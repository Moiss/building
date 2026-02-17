from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BuildingBillAllocation(models.Model):
    """
    Distribución de una factura de proveedor a obras.
    Registro persistente que vincula account.move con las obras.
    Contiene las líneas de distribución y referencia a los
    gastos reales generados.
    """
    _name = 'building.bill.allocation'
    _description = 'Distribución de Factura a Obras'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        help='Referencia automática: DIST-{factura}'
    )

    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        ondelete='cascade',
        index=True,
        readonly=True,
        domain="[('move_type', 'in', ['in_invoice', 'in_refund']), ('state', '=', 'posted')]"
    )

    date = fields.Date(
        string='Fecha Distribución',
        default=fields.Date.context_today,
        required=True,
        readonly=True
    )

    state = fields.Selection(
        [('active', 'Activa'),
         ('cancelled', 'Cancelada')],
        default='active',
        required=True,
        tracking=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='move_id.company_id',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='move_id.currency_id',
        store=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='move_id.partner_id',
        store=True,
        string='Proveedor'
    )

    move_amount_total = fields.Monetary(
        string='Total Factura',
        related='move_id.amount_total',
        currency_field='currency_id'
    )

    line_ids = fields.One2many(
        'building.bill.allocation.line',
        'allocation_id',
        string='Distribución',
        readonly=True
    )

    amount_total = fields.Monetary(
        string='Total Distribuido',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )

    real_line_ids = fields.One2many(
        'building.real.line',
        'bill_allocation_id',
        string='Gastos Reales Generados',
        readonly=True
    )

    real_line_count = fields.Integer(
        compute='_compute_real_line_count'
    )

    analytic_line_ids = fields.One2many(
        'account.analytic.line',
        'building_allocation_id',
        string='Líneas Analíticas'
    )

    @api.depends('move_id', 'move_id.name')
    def _compute_name(self):
        for alloc in self:
            alloc.name = 'DIST-%s' % (alloc.move_id.name or 'Nuevo')

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_totals(self):
        for alloc in self:
            alloc.amount_total = sum(alloc.line_ids.mapped('amount'))

    @api.depends('real_line_ids')
    def _compute_real_line_count(self):
        for alloc in self:
            alloc.real_line_count = len(alloc.real_line_ids)

    def action_cancel(self):
        """Cancela la distribución y elimina gastos reales generados."""
        for alloc in self:
            if alloc.state == 'cancelled':
                raise UserError(_('Ya está cancelada.'))
            # Eliminar gastos reales y analíticos
            if alloc.real_line_ids:
                alloc.real_line_ids.unlink()
            if alloc.analytic_line_ids:
                alloc.analytic_line_ids.unlink()
                
            alloc.write({'state': 'cancelled'})
            # Actualizar flag en factura
            remaining = alloc.move_id.building_allocation_ids.filtered(
                lambda a: a.state == 'active' and a.id != alloc.id
            )
            if not remaining:
                alloc.move_id.has_building_allocation = False
            alloc.message_post(body=_('Distribución cancelada. Gastos reales eliminados.'))

    def action_view_real_lines(self):
        self.ensure_one()
        return {
            'name': _('Gastos Reales'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.real.line',
            'view_mode': 'list,form',
            'domain': [('bill_allocation_id', '=', self.id)],
        }


class BuildingBillAllocationLine(models.Model):
    """Línea individual de distribución: obra + partida + monto."""
    _name = 'building.bill.allocation.line'
    _description = 'Línea de Distribución a Obra'
    _order = 'sequence, id'

    allocation_id = fields.Many2one(
        'building.bill.allocation',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(default=10)

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        index=True
    )

    budget_id = fields.Many2one(
        'building.budget',
        string='Presupuesto',
        help='Presupuesto al que pertenece la partida',
        domain="[('work_id', '=', work_id), ('budget_type', '!=', 'consolidated')]"
    )

    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        domain="[('work_id', '=', work_id), ('budget_id', '=', budget_id)]",
        help='Partida presupuestaria (opcional)'
    )

    description = fields.Char(string='Concepto')

    amount = fields.Monetary(
        string='Monto',
        currency_field='currency_id',
        required=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='allocation_id.currency_id',
        store=True
    )
