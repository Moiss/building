from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BuildingAllocateBillWizard(models.TransientModel):
    """
    Wizard para distribuir una factura de proveedor a obras.
    Permite agregar N líneas con obra, partida, monto o porcentaje.
    Al confirmar genera la distribución persistente y los gastos reales.
    """
    _name = 'building.allocate.bill.wizard'
    _description = 'Wizard - Aplicar Factura a Obra'

    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True,
        readonly=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='move_id.partner_id',
        string='Proveedor',
        readonly=True
    )

    amount_total = fields.Monetary(
        string='Total Factura',
        readonly=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='move_id.currency_id'
    )

    line_ids = fields.One2many(
        'building.allocate.bill.wizard.line',
        'wizard_id',
        string='Distribución'
    )

    amount_distributed = fields.Monetary(
        string='Distribuido',
        compute='_compute_distribution',
        currency_field='currency_id'
    )

    amount_pending = fields.Monetary(
        string='Pendiente',
        compute='_compute_distribution',
        currency_field='currency_id'
    )

    is_fully_distributed = fields.Boolean(
        compute='_compute_distribution'
    )

    # Info de distribuciones previas
    has_previous_allocation = fields.Boolean(
        compute='_compute_previous_allocation'
    )

    previous_allocated_amount = fields.Monetary(
        compute='_compute_previous_allocation',
        currency_field='currency_id'
    )

    @api.depends('line_ids', 'line_ids.amount', 'amount_total')
    def _compute_distribution(self):
        for wiz in self:
            distributed = sum(wiz.line_ids.mapped('amount'))
            wiz.amount_distributed = distributed
            # Considerar distribuciones previas activas
            prev = sum(wiz.move_id.building_allocation_ids.filtered(
                lambda a: a.state == 'active'
            ).mapped('amount_total'))
            wiz.amount_pending = wiz.amount_total - prev - distributed
            wiz.is_fully_distributed = abs(wiz.amount_pending) < 0.01

    @api.depends('move_id')
    def _compute_previous_allocation(self):
        for wiz in self:
            prev = wiz.move_id.building_allocation_ids.filtered(
                lambda a: a.state == 'active'
            )
            wiz.has_previous_allocation = bool(prev)
            wiz.previous_allocated_amount = sum(prev.mapped('amount_total'))

    def action_confirm(self):
        """
        Confirma la distribución:
        1. Valida que haya líneas y que los montos sean correctos
        2. Crea building.bill.allocation con sus líneas
        3. Genera building.real.line por cada línea
        4. Marca la factura con has_building_allocation = True
        5. Retorna a la factura
        """
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_('Agregue al menos una línea de distribución.'))
        
        for line in self.line_ids:
            if not line.work_id:
                raise UserError(_('Todas las líneas deben tener una Obra.'))
            if line.amount <= 0:
                raise UserError(_('Todos los montos deben ser mayores a 0.'))
        
        # Validar que no exceda el total disponible
        prev = sum(self.move_id.building_allocation_ids.filtered(
            lambda a: a.state == 'active'
        ).mapped('amount_total'))
        new_total = sum(self.line_ids.mapped('amount'))
        available = self.move_id.amount_total - prev
        if new_total > (available + 0.01):
            raise UserError(_(
                'El monto a distribuir (%s) excede el disponible (%s).'
            ) % (new_total, available))
        
        # 1. Crear distribución persistente
        allocation = self.env['building.bill.allocation'].create({
            'move_id': self.move_id.id,
            'date': fields.Date.context_today(self),
        })
        
        # 2. Crear líneas de distribución
        for line in self.line_ids:
            self.env['building.bill.allocation.line'].create({
                'allocation_id': allocation.id,
                'work_id': line.work_id.id,
                'budget_id': line.budget_id.id if line.budget_id else False,
                'budget_line_id': line.budget_line_id.id if line.budget_line_id else False,
                'description': line.description,
                'amount': line.amount,
            })
        
        # 3. Generar gastos reales (building.real.line)
        for line in self.line_ids:
            self.env['building.real.line'].create({
                'work_id': line.work_id.id,
                'budget_line_id': line.budget_line_id.id if line.budget_line_id else False,
                'amount': line.amount,
                'date': fields.Date.context_today(self),
                'name': 'Fact. %s - %s' % (
                    self.move_id.name or '',
                    line.description or self.partner_id.name or ''
                ),
                'bill_allocation_id': allocation.id,
            })
        
        # 4. Marcar factura
        self.move_id.has_building_allocation = True
        
        # 5. Mensaje
        allocation.message_post(body=_(
            'Distribución creada: %s líneas, monto total %s'
        ) % (len(self.line_ids), new_total))
        
        # 6. Retornar a la factura
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'main',
        }


class BuildingAllocateBillWizardLine(models.TransientModel):
    _name = 'building.allocate.bill.wizard.line'
    _description = 'Línea Wizard Distribución'

    wizard_id = fields.Many2one(
        'building.allocate.bill.wizard',
        required=True,
        ondelete='cascade'
    )

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True
    )

    budget_id = fields.Many2one(
        'building.budget',
        string='Presupuesto',
        domain="[('work_id', '=', work_id), ('budget_type', '!=', 'consolidated'), ('state', '=', 'validated')]",
        help='Presupuesto de la obra (excluye consolidados)',
    )

    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        domain="[('work_id', '=', work_id), ('budget_id', '=', budget_id), ('budget_id.budget_type', '!=', 'consolidated')]"
    )

    description = fields.Char(string='Concepto')

    distribution_type = fields.Selection(
        [('amount', 'Por Monto'), ('percent', 'Por Porcentaje')],
        default='amount',
        required=True
    )

    percent = fields.Float(string='%')

    amount = fields.Monetary(
        string='Monto',
        compute='_compute_amount',
        store=True,
        readonly=False,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id'
    )

    @api.depends('distribution_type', 'percent', 'wizard_id.amount_total')
    def _compute_amount(self):
        for line in self:
            if line.distribution_type == 'percent' and line.wizard_id:
                line.amount = (line.percent / 100.0) * line.wizard_id.amount_total

    @api.onchange('work_id')
    def _onchange_work_id(self):
        self.budget_id = False
        self.budget_line_id = False

    @api.onchange('budget_id')
    def _onchange_budget_id(self):
        self.budget_line_id = False
