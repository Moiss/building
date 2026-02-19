from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    building_use_analytic = fields.Boolean(
        string='Activar contabilidad analítica por obra',
        config_parameter='building.use_analytic',
        default=False,
    )

    building_analytic_mode = fields.Selection(
        [
            ('auto', 'Automático al crear obra'),
            ('manual', 'Manual con botón'),
            ('both', 'Ambos'),
        ],
        string='Modo de creación analítica',
        config_parameter='building.analytic_mode',
        default='both',
    )

    # === SEGURIDAD (CIFRADO) ===
    building_encryption_key = fields.Char(
        string='Clave de Cifrado (Fernet)',
        config_parameter='building.encryption.key',
        help='Clave utilizada para cifrar/descifrar las API Keys.',
        readonly=True
    )

    def action_generate_encryption_key(self):
        """Genera una nueva clave de cifrado si no existe."""
        encryption_service = self.env['building.encryption.service']
        key = encryption_service.generate_encryption_key()
        
        # Guardar en ir.config_parameter
        self.env['ir.config_parameter'].set_param('building.encryption.key', key)
        
        # Actualizar vista
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
