# -*- coding: utf-8 -*-
import requests
import json
import logging
from odoo import models, _, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BuildingAIService(models.AbstractModel):
    _name = 'building.ai.service'
    _description = 'Servicio de Conexión IA (Claude/OpenAI/Gemini)'

    def send_message(self, messages, system_prompt, work_id=False):
        """
        Envía un mensaje a la IA configurada y retorna la respuesta.
        
        Args:
            messages (list): Lista de dicts [{'role': 'user'|'assistant', 'content': str}]
            system_prompt (str): Instrucciones del sistema.
            work_id (int, optional): ID de la obra para buscar configuración específica.
            
        Returns:
            str: Contenido de la respuesta de la IA.
        """
        # 1. Obtener configuración
        Config = self.env['building.ai.config']
        if work_id:
            # Intentar buscar por todos los proveedores en orden de preferencia: Claude > OpenAI > Gemini
            config = False
            for provider in ['claude', 'openai', 'gemini']:
                config = Config.get_config_for_work(work_id, provider)
                if config: break
        else:
            # Buscar configuración genérica activa de la compañía
            # Prioridad: Claude > OpenAI > Gemini
            domain = [
                ('company_id', '=', self.env.company.id),
                ('active', '=', True),
                ('work_id', '=', False)
            ]
            configs = Config.search(domain)
            # Ordenar manual (Claude primero)
            config = next((c for c in configs if c.provider == 'claude'), None)
            if not config:
                config = next((c for c in configs if c.provider == 'openai'), None)
            if not config:
                config = next((c for c in configs if c.provider == 'gemini'), None)

        if not config:
            raise UserError(_("No se encontró una configuración activa de IA (Claude, OpenAI o Gemini)."))

        api_key = config.get_decrypted_api_key()
        if not api_key:
            raise UserError(_("La API Key no está configurada o no se pudo descifrar."))

        # 2. Despachar al proveedor
        try:
            if config.provider == 'claude':
                return self._call_claude(api_key, config.model_name, messages, system_prompt)
            elif config.provider == 'openai':
                return self._call_openai(api_key, config.model_name, messages, system_prompt)
            elif config.provider == 'gemini':
                return self._call_gemini(api_key, config.model_name, messages, system_prompt)
            else:
                raise UserError(_("Proveedor no soportado: %s") % config.provider)
        except requests.exceptions.Timeout:
            raise UserError(_("La solicitud a la IA excedió el tiempo de espera (120s). Intenta de nuevo."))
        except Exception as e:
            _logger.error("Error AI Service: %s", str(e))
            raise UserError(_("Error al conectar con la IA: %s") % str(e))

    def _call_claude(self, api_key, model, messages, system_prompt):
        """Llamada a Anthropic Claude API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Claude requiere formato específico de roles
        # System prompt va separado
        payload = {
            "model": model,
            "max_tokens": 8192,
            "temperature": 0.3,
            "system": system_prompt,
            "messages": messages
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_json = response.json()
                error_msg = error_json.get('error', {}).get('message', error_msg)
            except: pass
            raise Exception(f"Claude API Error ({response.status_code}): {error_msg}")
            
        result = response.json()
        return result['content'][0]['text']

    def _call_openai(self, api_key, model, messages, system_prompt):
        """Llamada a OpenAI GPT API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenAI incluye system prompt en messages
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        payload = {
            "model": model,
            "messages": full_messages,
            "max_completion_tokens": 8192, # Validar si es max_tokens para modelos nuevos
            "temperature": 0.3
        }
        
        # Ajuste para modelos o1/o3 que no soportan system role a veces, pero gpt-5.2 debería
        # Asumimos estándar chat completion
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_json = response.json()
                error_msg = error_json.get('error', {}).get('message', error_msg)
            except: pass
            raise Exception(f"OpenAI API Error ({response.status_code}): {error_msg}")
            
        result = response.json()
        return result['choices'][0]['message']['content']

    def _call_gemini(self, api_key, model, messages, system_prompt):
        """Llamada a Google Gemini API."""
        base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        url = f"{base_url}/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Mapeo de roles para Gemini (user/model)
        gemini_contents = []
        for msg in messages:
            role = 'user' if msg['role'] == 'user' else 'model'
            gemini_contents.append({
                "role": role,
                "parts": [{"text": msg['content']}]
            })
            
        payload = {
            "contents": gemini_contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192,
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
             # Gemini errors
            error_msg = response.text
            try:
                error_json = response.json()
                error_msg = error_json.get('error', {}).get('message', error_msg)
            except: pass
            raise Exception(f"Gemini API Error ({response.status_code}): {error_msg}")
            
        result = response.json()
        # Verificar response structure
        if 'candidates' in result and result['candidates']:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                return candidate['content']['parts'][0]['text']
        
        raise Exception("Respuesta vacía o inesperada de Gemini.")
