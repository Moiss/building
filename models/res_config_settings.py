from odoo import models, fields, api, _

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

    building_encryption_key = fields.Char(
        string='Clave de Cifrado (API Keys)',
        config_parameter='building.encryption_key',
        help='Clave utilizada para cifrar las API Keys de los servicios de IA.',
        readonly=False,
    )

    def action_generate_encryption_key(self):
        """Genera una nueva clave de cifrado y la asigna."""
        service = self.env['building.encryption.service']
        key = service.generate_encryption_key()
        self.env['ir.config_parameter'].set_param('building.encryption_key', key)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Clave Generada'),
                'message': _('Se ha generado y guardado una nueva clave de cifrado. La página se recargará.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
