# -*- coding: utf-8 -*-
import requests
import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

CONNECTION_TIMEOUT = 30  # Timeout mayor para generación de contenido

class BuildingAIService(models.Model):
    _name = 'building.ai.service'
    _description = 'Servicio de Integración IA'
    # No store=True fields needed here, just logic service
    
    def send_message(self, history, system_prompt, work_id=False):
        """
        Envía un mensaje al proveedor configurado y retorna la respuesta.
        
        Args:
            history (list): Lista de dicts [{'role': 'user'/'assistant', 'content': '...'}, ...]
            system_prompt (str): Prompt del sistema
            work_id (int, optional): ID de la obra para buscar configuración específica
            
        Returns:
            str: Contenido de la respuesta de la IA
        """
        # 1. Determinar Configuración Activa
        # Buscar config de Gemini (prioridad 1 si existe)
        config_gemini = self.env['building.ai.config'].get_config_for_work(work_id, 'gemini')
        if config_gemini:
            return self._call_gemini(config_gemini, history, system_prompt)
            
        # Buscar config de OpenAI (prioridad 2 si existe)
        config_openai = self.env['building.ai.config'].get_config_for_work(work_id, 'openai')
        if config_openai:
            return self._call_openai(config_openai, history, system_prompt)

        # Buscar config de Claude (prioridad 3 si existe)
        config_claude = self.env['building.ai.config'].get_config_for_work(work_id, 'claude')
        if config_claude:
            return self._call_claude(config_claude, history, system_prompt)
            
        raise UserError(_('No se encontró ninguna configuración de IA activa (Gemini, OpenAI o Claude). '
                          'Por favor configure un proveedor en Ajustes o Configuración de IA.'))

    def _call_gemini(self, config, history, system_prompt):
        """Llamada a API de Google Gemini."""
        api_key = config.get_decrypted_api_key()
        model = config.model_name or 'gemini-1.5-pro'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        
        # Convertir historial a formato Gemini
        # Gemini usa "parts": [{"text": "..."}] y roles "user"/"model"
        contents = []
        
        # System instruction va separado en la API v1beta
        # Pero podemos inyectarlo al inicio si el modelo no soporta system_instruction explícito en esta ruta
        # Para robustez, lo ponemos como primer mensaje de 'user' o 'system' si soportado.
        # En v1beta REST, systemInstruction se pasa en top level.
        
        # Mapear roles: user -> user, assistant -> model
        for msg in history:
            role = 'user' if msg['role'] == 'user' else 'model'
            contents.append({
                'role': role,
                'parts': [{'text': msg['content']}]
            })
            
        headers = {'Content-Type': 'application/json'}
        params = {'key': api_key}
        
        payload = {
            'contents': contents,
            'systemInstruction': {
                'parts': [{'text': system_prompt}]
            },
            'generationConfig': {
                'temperature': 0.7,
                #'maxOutputTokens': 8192,
            }
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=CONNECTION_TIMEOUT)
            response.raise_for_status() # Raise error for 4xx/5xx
            
            result = response.json()
            # Extraer texto
            # candidates[0].content.parts[0].text
            try:
                candidate = result['candidates'][0]
                content = candidate['content']['parts'][0]['text']
                return content
            except (KeyError, IndexError):
                _logger.error("Gemini response format unexpected: %s", result)
                raise UserError(_('Respuesta inesperada de Gemini API.'))
                
        except requests.exceptions.RequestException as e:
            _logger.error("Gemini API Error: %s", str(e))
            raise UserError(_('Error al conectar con Gemini: %s') % str(e))

    def _call_openai(self, config, history, system_prompt):
        """Llamada a API de OpenAI GPT."""
        api_key = config.get_decrypted_api_key()
        model = config.model_name or 'gpt-4o'
        url = 'https://api.openai.com/v1/chat/completions'
        
        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(history) # history ya tiene formato {'role': '...', 'content': '...'}
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': messages,
            'temperature': 0.7
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=CONNECTION_TIMEOUT)
            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', str(response.status_code))
                raise UserError(_('OpenAI Error: %s') % error_msg)
                
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            _logger.error("OpenAI API Error: %s", str(e))
            raise UserError(_('Error al conectar con OpenAI: %s') % str(e))

    def _call_claude(self, config, history, system_prompt):
        """Llamada a API de Anthropic Claude."""
        api_key = config.get_decrypted_api_key()
        model = config.model_name or 'claude-3-sonnet-20240229'
        url = 'https://api.anthropic.com/v1/messages'
        
        # Claude system prompt va en 'system' parameter top level
        # Messages list solo user/assistant
        
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        payload = {
            'model': model,
            'max_tokens': 4096,
            'system': system_prompt,
            'messages': history,
            'temperature': 0.7
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=CONNECTION_TIMEOUT)
            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_json = response.json()
                    error_msg = error_json.get('error', {}).get('message', error_msg)
                except:
                    pass
                raise UserError(_('Claude Error: %s') % error_msg)
                
            result = response.json()
            return result['content'][0]['text']
            
        except requests.exceptions.RequestException as e:
            _logger.error("Claude API Error: %s", str(e))
            raise UserError(_('Error al conectar con Claude: %s') % str(e))
