# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class BuildingWorkCost(models.Model):
    """
    Modelo de Costos Operativos de Obra (Etapa 4.1).
    Permite registrar gastos presupuestados (ligados a partida) y adicionales (indirectos).
    NO afecta avance físico.
    """
    _name = 'building.work.cost'
    _description = 'Costo Operativo de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Descripción Corta',
        required=True,
        tracking=True,
        help='Referencia o concepto breve del costo'
    )

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa',
        domain="[('work_id', '=', work_id)]",
        index=True,
        tracking=True,
        help='Etapa opcional para clasificación'
    )

    cost_type = fields.Selection([
        ('budgeted', 'Presupuestado'),
        ('additional', 'Adicional / Indirecto')
    ], string='Tipo de Costo', required=True, default='additional', tracking=True)

    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida Presupuestaria',
        domain="[('work_id', '=', work_id)]",
        index=True,
        tracking=True,
        help='Opcional: vincule a una partida del presupuesto si este gasto corresponde a alguna'
    )

    date = fields.Date(
        string='Fecha',
        default=fields.Date.context_today,
        required=True,
        index=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        help='Producto o servicio del gasto'
    )

    description = fields.Text(string='Descripción Detallada')

    qty = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida'
    )

    unit_cost = fields.Monetary(
        string='Costo Unitario',
        currency_field='currency_id',
        default=0.0,
        required=True
    )

    amount = fields.Monetary(
        string='Monto Total',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='work_id.currency_id',
        store=True,
        readonly=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='work_id.company_id',
        store=True,
        readonly=True
    )
    
    active = fields.Boolean(default=True)

    # === COMPUTE ===
    @api.depends('qty', 'unit_cost')
    def _compute_amount(self):
        for record in self:
            record.amount = record.qty * record.unit_cost

    # === ONCHANGE ===
    @api.onchange('work_id')
    def _onchange_work_id(self):
        if self.stage_id and self.stage_id.work_id != self.work_id:
            self.stage_id = False
        if self.budget_line_id and self.budget_line_id.work_id != self.work_id:
            self.budget_line_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.uom_id:
                self.uom_id = self.product_id.uom_id
            if not self.name:
                self.name = self.product_id.name
            # Sugerir costo estándar si no hay uno
            if self.unit_cost == 0.0:
                self.unit_cost = self.product_id.standard_price

    # === CONSTRAINTS ===
    @api.constrains('work_id', 'stage_id', 'budget_line_id')
    def _check_scope_integrity(self):
        for record in self:
            if record.stage_id and record.stage_id.work_id != record.work_id:
                raise ValidationError(_("La etapa seleccionada no pertenece a la obra."))
            if record.budget_line_id and record.budget_line_id.work_id != record.work_id:
                raise ValidationError(_("La partida seleccionada no pertenece a la obra."))

    # === CRUD OVERRIDES (TRIGGER ENGINE) ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['cost_type'] = 'additional'
        records = super().create(vals_list)
        records.mapped('work_id')._recompute_cost_totals()
        return records

    def write(self, vals):
        # Optimización: solo recomponer si cambian campos relevantes
        recompute = any(f in vals for f in ['amount', 'qty', 'unit_cost', 'cost_type', 'work_id', 'active'])
        res = super().write(vals)
        if recompute:
            self.mapped('work_id')._recompute_cost_totals()
        return res

    def unlink(self):
        works = self.mapped('work_id')
        res = super().unlink()
        works._recompute_cost_totals()
        return res