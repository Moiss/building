# -*- coding: utf-8 -*-
"""
Modelo: Configuración de IA (building.ai.config)
Almacena las API Keys cifradas y configuración de modelos IA.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BuildingAIConfig(models.Model):
    """
    Configuración de Asistente IA por compañía/obra.
    Las API Keys se almacenan cifradas usando Fernet.
    """
    _name = 'building.ai.config'
    _description = 'Configuración de Asistente IA'
    _order = 'company_id, work_id, provider'

    # === CAMPOS DE SCOPE ===
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        index=True,
        default=lambda self: self.env.company
    )
    
    work_id = fields.Many2one(
        'building.work',
        string='Obra (Override)',
        index=True,
        help='Si se especifica, esta configuración aplica solo a esta obra'
    )
    
    # === CAMPOS DE CONFIGURACIÓN ===
    provider = fields.Selection([
        ('gemini', 'Gemini (Google)'),
        ('openai', 'ChatGPT (OpenAI)'),
    ], string='Proveedor', required=True)
    
    model_name = fields.Char(
        string='Modelo',
        required=True,
        help='Nombre del modelo de IA (ej: gemini-1.5-pro, gpt-4o)'
    )
    
    # === CAMPOS DE API KEY (CIFRADOS) ===
    api_key_encrypted = fields.Text(
        string='API Key (Cifrada)',
        required=True,
        help='La API Key cifrada con Fernet'
    )
    
    api_key_last4 = fields.Char(
        string='Últimos 4 caracteres',
        readonly=True,
        help='Últimos 4 caracteres de la API Key (para verificación)'
    )
    
    # === CAMPOS DE ESTADO ===
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    updated_by = fields.Many2one(
        'res.users',
        string='Actualizado por',
        readonly=True
    )
    
    updated_at = fields.Datetime(
        string='Última actualización',
        readonly=True
    )

    # === RESTRICCIÓN ÚNICA (API constraint) ===
    @api.constrains('company_id', 'work_id', 'provider')
    def _check_unique_config_per_scope_provider(self):
        """Asegura una sola configuración por proveedor y scope."""
        for record in self:
            domain = [
                ('company_id', '=', record.company_id.id),
                ('work_id', '=', record.work_id.id if record.work_id else False),
                ('provider', '=', record.provider),
                ('id', '!=', record.id),
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    _('Solo puede existir una configuración por proveedor y scope (compañía/obra).')
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Override para registrar usuario y fecha de creación."""
        for vals in vals_list:
            vals['updated_by'] = self.env.uid
            vals['updated_at'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        """Override para registrar usuario y fecha de actualización."""
        vals['updated_by'] = self.env.uid
        vals['updated_at'] = fields.Datetime.now()
        return super().write(vals)

    @api.model
    def get_config_for_work(self, work_id, provider):
        """
        Obtiene la configuración de IA para una obra específica.
        Primero busca config específica de obra, luego de compañía.
        
        Args:
            work_id: ID de la obra
            provider: 'gemini' o 'openai'
            
        Returns:
            building.ai.config record o False
        """
        work = self.env['building.work'].browse(work_id)
        if not work.exists():
            return False
        
        # Buscar config específica de obra
        config = self.search([
            ('work_id', '=', work_id),
            ('provider', '=', provider),
            ('active', '=', True),
        ], limit=1)
        
        if config:
            return config
        
        # Buscar config de compañía (sin obra específica)
        config = self.search([
            ('company_id', '=', work.company_id.id),
            ('work_id', '=', False),
            ('provider', '=', provider),
            ('active', '=', True),
        ], limit=1)
        
        return config if config else False

    def get_decrypted_api_key(self):
        """
        Obtiene la API Key descifrada.
        ADVERTENCIA: Usar con cuidado, no loguear.
        
        Returns:
            str: La API Key en texto plano
        """
        self.ensure_one()
        encryption = self.env['building.encryption.service']
        return encryption.decrypt_api_key(self.api_key_encrypted)
