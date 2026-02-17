from odoo import models, fields

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    building_allocation_id = fields.Many2one(
        'building.bill.allocation',
        string='Distribución de Obra',
        ondelete='cascade',
        index=True
    )
