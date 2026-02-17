from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMoveBuilding(models.Model):
    """
    Herencia de account.move para agregar campos de
    integración con el módulo de obras (building).
    """
    _inherit = 'account.move'

    has_building_allocation = fields.Boolean(
        string='Aplicada a Obra',
        default=False,
        readonly=True,
        tracking=True,
        help='Indica si esta factura tiene distribución a obras'
    )

    building_allocation_ids = fields.One2many(
        'building.bill.allocation',
        'move_id',
        string='Distribuciones a Obra',
        readonly=True
    )

    building_allocation_count = fields.Integer(
        compute='_compute_building_allocation_count',
        string='# Distribuciones'
    )

    building_allocated_amount = fields.Monetary(
        string='Monto Aplicado a Obras',
        compute='_compute_building_allocation_count',
        currency_field='currency_id'
    )

    is_fully_allocated = fields.Boolean(
        string='Completamente Distribuida',
        compute='_compute_is_fully_allocated',
        store=True,
    )

    @api.depends('building_allocation_ids', 'building_allocation_ids.amount_total',
                 'building_allocation_ids.state', 'amount_total')
    def _compute_is_fully_allocated(self):
        """Verifica si la factura ya tiene el 100% distribuido."""
        for move in self:
            allocated = sum(move.building_allocation_ids.filtered(
                lambda a: a.state == 'active'
            ).mapped('amount_total'))
            move.is_fully_allocated = allocated >= (move.amount_total - 0.01)

    @api.depends('building_allocation_ids', 'building_allocation_ids.amount_total')
    def _compute_building_allocation_count(self):
        for move in self:
            allocations = move.building_allocation_ids
            move.building_allocation_count = len(allocations)
            move.building_allocated_amount = sum(allocations.mapped('amount_total'))

    def action_open_allocate_wizard(self):
        """Abre wizard para distribuir esta factura a obras."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(_('Solo se pueden aplicar facturas de proveedor a obras.'))
        if self.state != 'posted':
            raise UserError(_('La factura debe estar confirmada/publicada.'))
        # NUEVO: Verificar si ya está completamente distribuida
        if self.is_fully_allocated:
            raise UserError(_(
                'Esta factura ya está completamente distribuida a obras. '
                'Si necesita redistribuir, cancele la distribución existente primero.'
            ))
        return {
            'name': _('Aplicar a Obra'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.allocate.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_amount_total': self.amount_total,
            },
        }

    def action_view_building_allocations(self):
        """Ver distribuciones a obras de esta factura."""
        self.ensure_one()
        return {
            'name': _('Distribuciones a Obra - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'building.bill.allocation',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
        }
