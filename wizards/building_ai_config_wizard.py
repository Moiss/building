# -*- coding: utf-8 -*-
"""
Wizard: Configuración del Asistente IA (building.ai.config.wizard)
Permite configurar API Keys y probar conexiones con Gemini y OpenAI.
"""

import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Timeout para pruebas de conexión (segundos)
CONNECTION_TIMEOUT = 10


class BuildingAIConfigWizard(models.TransientModel):
    """
    Wizard para configurar el Asistente IA.
    Permite gestionar API Keys de Gemini y OpenAI.
    """
    _name = 'building.ai.config.wizard'
    _description = 'Configuración del Asistente IA'

    # === CAMPOS DE CONTEXTO ===
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        readonly=True
    )
    
    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        readonly=True,
        help='Obra desde la que se abrió el wizard'
    )
    
    use_work_override = fields.Boolean(
        string='Configuración específica para esta Obra',
        default=False,
        help='Si está activo, la configuración aplica solo a esta obra'
    )

    # === CAMPOS DE CLAUDE (ANTHROPIC) ===
    claude_api_key = fields.Char(
        string='API Key (Claude)',
        help='Ingrese su API Key de Anthropic (sk-ant-...)'
    )

    claude_model = fields.Selection([
        ('claude-3-opus-20240229', 'Claude 3 Opus'),
        ('claude-3-sonnet-20240229', 'Claude 3 Sonnet'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku'),
    ], string='Modelo Claude', default='claude-3-sonnet-20240229')

    claude_status = fields.Selection([
        ('not_configured', 'No Configurado'),
        ('configured', 'Configurado'),
    ], string='Estado Claude', compute='_compute_claude_status')

    claude_last4 = fields.Char(
        string='Claude (últimos 4)',
        compute='_compute_claude_status'
    )

    # === CAMPOS DE GEMINI ===
    gemini_api_key = fields.Char(
        string='API Key (Gemini)',
        help='Ingrese su API Key de Google AI (Gemini)'
    )
    
    gemini_model = fields.Selection([
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
    ], string='Modelo Gemini', default='gemini-1.5-pro')
    
    gemini_status = fields.Selection([
        ('not_configured', 'No Configurado'),
        ('configured', 'Configurado'),
    ], string='Estado Gemini', compute='_compute_gemini_status')
    
    gemini_last4 = fields.Char(
        string='Gemini (últimos 4)',
        compute='_compute_gemini_status'
    )

    # === CAMPOS DE OPENAI ===
    openai_api_key = fields.Char(
        string='API Key (OpenAI)',
        help='Ingrese su API Key de OpenAI'
    )
    
    openai_model = fields.Selection([
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
        ('gpt-4.1-mini', 'GPT-4.1 Mini'),
    ], string='Modelo OpenAI', default='gpt-4o')
    
    openai_status = fields.Selection([
        ('not_configured', 'No Configurado'),
        ('configured', 'Configurado'),
    ], string='Estado OpenAI', compute='_compute_openai_status')
    
    openai_last4 = fields.Char(
        string='OpenAI (últimos 4)',
        compute='_compute_openai_status'
    )

    # === CAMPOS DE PERMISOS ===
    can_edit = fields.Boolean(
        string='Puede Editar',
        compute='_compute_can_edit'
    )

    @api.depends_context('uid')
    def _compute_can_edit(self):
        """Determina si el usuario puede editar la configuración."""
        user = self.env.user
        can_edit = (
            user.has_group('building_dashboard.group_building_director') or
            user.has_group('building_dashboard.group_building_admin') or
            user.has_group('base.group_system')
        )
        for wizard in self:
            wizard.can_edit = can_edit

    @api.depends('company_id', 'work_id', 'use_work_override')
    def _compute_claude_status(self):
        """Obtiene el estado de configuración de Claude."""
        for wizard in self:
            config = self._get_existing_config(wizard, 'claude')
            if config:
                wizard.claude_status = 'configured'
                wizard.claude_last4 = config.api_key_last4 or '****'
            else:
                wizard.claude_status = 'not_configured'
                wizard.claude_last4 = ''

    @api.depends('company_id', 'work_id', 'use_work_override')
    def _compute_gemini_status(self):
        """Obtiene el estado de configuración de Gemini."""
        ConfigModel = self.env['building.ai.config']
        for wizard in self:
            config = self._get_existing_config(wizard, 'gemini')
            if config:
                wizard.gemini_status = 'configured'
                wizard.gemini_last4 = config.api_key_last4 or '****'
            else:
                wizard.gemini_status = 'not_configured'
                wizard.gemini_last4 = ''

    @api.depends('company_id', 'work_id', 'use_work_override')
    def _compute_openai_status(self):
        """Obtiene el estado de configuración de OpenAI."""
        for wizard in self:
            config = self._get_existing_config(wizard, 'openai')
            if config:
                wizard.openai_status = 'configured'
                wizard.openai_last4 = config.api_key_last4 or '****'
            else:
                wizard.openai_status = 'not_configured'
                wizard.openai_last4 = ''

    def _get_existing_config(self, wizard, provider):
        """
        Obtiene la configuración existente para el scope actual.
        """
        ConfigModel = self.env['building.ai.config']
        domain = [
            ('company_id', '=', wizard.company_id.id),
            ('provider', '=', provider),
            ('active', '=', True),
        ]
        if wizard.use_work_override and wizard.work_id:
            domain.append(('work_id', '=', wizard.work_id.id))
        else:
            domain.append(('work_id', '=', False))
        
        return ConfigModel.search(domain, limit=1)

    # === ACCIONES DE PRUEBA DE CONEXIÓN ===
    def action_test_claude_connection(self):
        """
        Prueba la conexión con la API de Anthropic (Claude).
        """
        self.ensure_one()
        
        # Obtener API Key
        api_key = self.claude_api_key
        if not api_key:
            config = self._get_existing_config(self, 'claude')
            if config:
                api_key = config.get_decrypted_api_key()
        
        if not api_key:
            raise UserError(_('No hay API Key de Claude configurada.'))
        
        # Probar conexión simple (messages)
        url = 'https://api.anthropic.com/v1/messages'
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        payload = {
            'model': self.claude_model or 'claude-3-haiku-20240307',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=CONNECTION_TIMEOUT)
            
            if response.status_code == 200:
                return self._notify_success('Claude', self.claude_model)
            elif response.status_code == 401:
                return self._notify_error('Claude', 'API Key inválida')
            elif response.status_code == 429:
                return self._notify_error('Claude', 'Límite de cuota excedido')
            else:
                return self._notify_error('Claude', f'Error {response.status_code}')
                
        except requests.exceptions.Timeout:
            return self._notify_error('Claude', 'Timeout de conexión')
        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión Claude: %s', str(e))
            return self._notify_error('Claude', 'Error de conexión')

    def action_test_gemini_connection(self):
        """
        Prueba la conexión con la API de Gemini.
        """
        self.ensure_one()
        
        # Obtener API Key (de input o existente)
        api_key = self.gemini_api_key
        if not api_key:
            config = self._get_existing_config(self, 'gemini')
            if config:
                api_key = config.get_decrypted_api_key()
        
        if not api_key:
            raise UserError(_('No hay API Key de Gemini configurada.'))
        
        # Probar conexión
        model = self.gemini_model or 'gemini-1.5-pro'
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        
        headers = {'Content-Type': 'application/json'}
        params = {'key': api_key}
        payload = {
            'contents': [{'parts': [{'text': 'Hello'}]}],
            'generationConfig': {'maxOutputTokens': 1}
        }
        
        try:
            response = requests.post(
                url, 
                headers=headers,
                params=params,
                json=payload,
                timeout=CONNECTION_TIMEOUT
            )
            
            if response.status_code == 200:
                return self._notify_success('Gemini', model)
            elif response.status_code == 401:
                return self._notify_error('Gemini', 'API Key inválida')
            elif response.status_code == 429:
                return self._notify_error('Gemini', 'Límite de cuota excedido')
            else:
                return self._notify_error('Gemini', f'Error {response.status_code}')
                
        except requests.exceptions.Timeout:
            return self._notify_error('Gemini', 'Timeout de conexión')
        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión Gemini: %s', str(e))
            return self._notify_error('Gemini', 'Error de conexión')

    def action_test_openai_connection(self):
        """
        Prueba la conexión con la API de OpenAI.
        """
        self.ensure_one()
        
        # Obtener API Key
        api_key = self.openai_api_key
        if not api_key:
            config = self._get_existing_config(self, 'openai')
            if config:
                api_key = config.get_decrypted_api_key()
        
        if not api_key:
            raise UserError(_('No hay API Key de OpenAI configurada.'))
        
        # Probar conexión listando modelos
        url = 'https://api.openai.com/v1/models'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=CONNECTION_TIMEOUT)
            
            if response.status_code == 200:
                return self._notify_success('OpenAI', self.openai_model)
            elif response.status_code == 401:
                return self._notify_error('OpenAI', 'API Key inválida')
            elif response.status_code == 429:
                return self._notify_error('OpenAI', 'Límite de cuota excedido')
            else:
                return self._notify_error('OpenAI', f'Error {response.status_code}')
                
        except requests.exceptions.Timeout:
            return self._notify_error('OpenAI', 'Timeout de conexión')
        except requests.exceptions.RequestException as e:
            _logger.error('Error de conexión OpenAI: %s', str(e))
            return self._notify_error('OpenAI', 'Error de conexión')

    def _notify_success(self, provider, model):
        """Muestra notificación de éxito."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Conexión Exitosa'),
                'message': _('%s conectado correctamente (modelo: %s)') % (provider, model),
                'type': 'success',
                'sticky': False,
            }
        }

    def _notify_error(self, provider, error_msg):
        """Muestra notificación de error."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Error de Conexión'),
                'message': _('%s: %s') % (provider, error_msg),
                'type': 'danger',
                'sticky': True,
            }
        }

    # === ACCIÓN DE GUARDAR ===
    def action_save(self):
        """
        Guarda la configuración de ambos proveedores.
        Cifra las API Keys antes de guardarlas.
        """
        self.ensure_one()
        
        # Verificar permisos
        if not self.can_edit:
            raise UserError(
                _('No tiene permisos para modificar la configuración del Asistente IA.')
            )
        
        # Verificar que el cifrado esté configurado
        encryption = self.env['building.encryption.service']
        if not encryption.is_encryption_configured():
            raise UserError(
                _('El cifrado no está configurado.\n'
                  'Vaya a Ajustes > Building Dashboard y genere una clave de cifrado.')
            )
        
        # Determinar scope
        work_id = self.work_id.id if self.use_work_override and self.work_id else False
        
        # Guardar Gemini si hay API Key
        if self.gemini_api_key:
            self._save_provider_config(
                provider='gemini',
                api_key=self.gemini_api_key,
                model_name=self.gemini_model,
                work_id=work_id
            )
        
        # Guardar OpenAI si hay API Key
        if self.openai_api_key:
            self._save_provider_config(
                provider='openai',
                api_key=self.openai_api_key,
                model_name=self.openai_model,
                work_id=work_id
            )

        # Guardar Claude si hay API Key
        if self.claude_api_key:
            self._save_provider_config(
                provider='claude',
                api_key=self.claude_api_key,
                model_name=self.claude_model,
                work_id=work_id
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Configuración Guardada'),
                'message': _('Las API Keys han sido cifradas y guardadas correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _save_provider_config(self, provider, api_key, model_name, work_id):
        """
        Guarda o actualiza la configuración de un proveedor específico.
        """
        ConfigModel = self.env['building.ai.config']
        encryption = self.env['building.encryption.service']
        
        # Cifrar la API Key
        cipher_text, last4 = encryption.encrypt_api_key(api_key)
        
        # Buscar configuración existente
        domain = [
            ('company_id', '=', self.company_id.id),
            ('provider', '=', provider),
        ]
        if work_id:
            domain.append(('work_id', '=', work_id))
        else:
            domain.append(('work_id', '=', False))
        
        existing = ConfigModel.search(domain, limit=1)
        
        vals = {
            'api_key_encrypted': cipher_text,
            'api_key_last4': last4,
            'model_name': model_name,
            'active': True,
        }
        
        if existing:
            existing.write(vals)
        else:
            vals.update({
                'company_id': self.company_id.id,
                'work_id': work_id,
                'provider': provider,
            })
            ConfigModel.create(vals)
