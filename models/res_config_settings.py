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
