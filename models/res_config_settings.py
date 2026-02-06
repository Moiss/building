# -*- coding: utf-8 -*-
"""
Extensión de res.config.settings para Building Dashboard.
Permite configurar la clave maestra de cifrado.
"""

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    """
    Extensión de ajustes para configurar la clave de cifrado
    del módulo Building Dashboard.
    """
    _inherit = 'res.config.settings'

    # === CAMPO DE CLAVE DE CIFRADO ===
    building_encryption_key = fields.Char(
        string='Clave de Cifrado (Building)',
        config_parameter='building.encryption_key',
        help=(
            'Clave maestra para cifrar las API Keys del Asistente IA.\n'
            'IMPORTANTE: Esta clave es crítica para la seguridad.\n'
            '- Debe ser una clave Fernet válida (base64 de 32 bytes).\n'
            '- Use el botón "Generar Nueva Clave" para crear una.\n'
            '- Si la pierde, las API Keys guardadas NO podrán recuperarse.'
        )
    )

    # === CONFIGURACIÓN PRESUPUESTO VS REAL (FASE 3.4) ===
    budget_real_threshold_warning = fields.Float(
        string='Umbral Advertencia (%)',
        config_parameter='building.budget_real_threshold_warning',
        default=80.0,
        help='Porcentaje de gasto real sobre presupuesto para mostrar advertencia (Amarillo).'
    )

    budget_real_threshold_critical = fields.Float(
        string='Umbral Crítico (%)',
        config_parameter='building.budget_real_threshold_critical',
        default=100.0,
        help='Porcentaje de gasto real sobre presupuesto para mostrar alerta (Rojo).'
    )

    building_default_real_source = fields.Selection([
        ('internal', 'Interno (Plan A)'),
        ('accounting', 'Contabilidad (Plan B)'),
    ], string='Fuente por Defecto', config_parameter='building.default_real_source', default='internal')

    # Configuración Contable para Migración
    migration_journal_id = fields.Many2one(
        'account.journal',
        string='Diario para Migración',
        config_parameter='building.migration_journal_id',
        help='Diario contable donde se generará el asiento de migración histórica.'
    )

    migration_debit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Cargo (Gasto)',
        config_parameter='building.migration_debit_account_id',
        help='Cuenta donde se cargan los gastos migrados.'
    )

    migration_credit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Abono (Puente)',
        config_parameter='building.migration_credit_account_id',
        help='Cuenta puente contra la que se abonan los gastos migrados.'
    )

    def action_generate_encryption_key(self):
        """
        Genera una nueva clave de cifrado Fernet y la guarda en ir.config_parameter.
        Luego recarga la vista para mostrar el valor.
        """
        encryption = self.env['building.encryption.service']
        new_key = encryption.generate_encryption_key()
        
        # Actualizar el parámetro del sistema directamente
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('building.encryption_key', new_key)
        
        # Forzar commit para asegurar persistencia
        self.env.cr.commit()
        
        # Notificar al usuario y recargar la vista
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Clave Generada',
                'message': 'Se ha generado y guardado una nueva clave de cifrado. Recargue la página para verla.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }
