# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BuildingRealLine(models.Model):
    """
    Registro de Gastos Reales (Plan A).
    Permite la captura manual de costos cuando no hay integración contable.
    """
    _name = 'building.real.line'
    _description = 'Línea de Gasto Real'
    _order = 'date desc, id desc'

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa',
        domain="[('work_id', '=', work_id)]",
        index=True
    )
    
    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida Presupuestaria',
        required=True,
        domain="[('work_id', '=', work_id)]",
        ondelete='restrict',
        index=True
    )
    
    name = fields.Char(
        string='Concepto',
        required=True
    )
    
    amount = fields.Monetary(
        string='Monto Real',
        required=True,
        currency_field='currency_id'
    )

    budget_amount = fields.Float(
        string='Presupuestado',
        related='budget_line_id.amount',
        store=True,
        readonly=True,
        help='Monto total presupuestado para esta partida.'
    )

    difference = fields.Monetary(
        string='Diferencia',
        compute='_compute_difference',
        store=True,
        currency_field='currency_id',
        help='Diferencia: Presupuestado - Monto Real Actual.'
    )
    
    date = fields.Date(
        string='Fecha',
        default=fields.Date.context_today,
        required=True,
        index=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        related='work_id.company_id',
        store=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='work_id.currency_id',
        store=True
    )

    # === MIGRACIÓN ===
    is_migrated = fields.Boolean(
        string='Migrado a Contabilidad',
        default=False,
        readonly=True,
        copy=False,
        index=True
    )
    
    migrated_move_id = fields.Many2one(
        'account.move',
        string='Asiento Relacionado',
        readonly=True,
        copy=False
    )
    
    migrated_on = fields.Datetime(
        string='Fecha Migración',
        readonly=True
    )
    
    migrated_by = fields.Many2one(
        'res.users',
        string='Migrado por',
        readonly=True
    )

    migrated_by = fields.Many2one(
        'res.users',
        string='Migrado por',
        readonly=True
    )

    # === COMPUTE METHODS ===
    @api.depends('budget_amount', 'amount')
    def _compute_difference(self):
        for line in self:
            line.difference = line.budget_amount - line.amount

    @api.onchange('budget_line_id')
    def _onchange_budget_line_id(self):
        """Auto-asignar etapa según la partida seleccionada."""
        if self.budget_line_id and self.budget_line_id.stage_id:
            self.stage_id = self.budget_line_id.stage_id

    # === CONSTRAINTS ===
    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_('El monto real no puede ser negativo.'))

    @api.constrains('work_id', 'stage_id', 'budget_line_id')
    def _check_coherence(self):
        for line in self:
            if line.stage_id and line.stage_id.work_id != line.work_id:
                raise ValidationError(_('La etapa no pertenece a la obra seleccionada.'))
            if line.budget_line_id.work_id != line.work_id:
                raise ValidationError(_('La partida no pertenece a la obra seleccionada.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-asignar etapa si falta
            if 'budget_line_id' in vals and not vals.get('stage_id'):
                budget_line = self.env['building.budget.line'].browse(vals['budget_line_id'])
                if budget_line.stage_id:
                    vals['stage_id'] = budget_line.stage_id.id

            if 'work_id' in vals:
                work = self.env['building.work'].browse(vals['work_id'])
                # Bloquear captura interna si la fuente es contable y fecha > fecha corte
                if work.real_source == 'accounting' and work.real_cutover_date:
                    date_val = fields.Date.from_string(vals.get('date', fields.Date.context_today(self)))
                    if date_val >= work.real_cutover_date:
                         raise UserError(_(
                            'No se pueden crear registros internos con fecha posterior al corte (%s) '
                            'porque la obra usa fuente Contable.'
                        ) % work.real_cutover_date)
        records = super().create(vals_list)
        # Regenerar alertas de las obras afectadas (Regla 2: Gasto > Avance)
        works = records.mapped('work_id')
        for work in works:
            self.env['building.alert.engine'].rebuild_alerts(work.id)
        return records

    def write(self, vals):
        if 'is_migrated' not in vals: # Permitir cambios de sistema
             for line in self:
                if line.is_migrated:
                    raise UserError(_('No se puede modificar un gasto ya migrado a contabilidad.'))
        result = super().write(vals)
        # Regenerar alertas por cambios en monto
        works = self.mapped('work_id')
        for work in works:
            self.env['building.alert.engine'].rebuild_alerts(work.id)
        return result

    def unlink(self):
        for line in self:
            if line.is_migrated:
                raise UserError(_('No se puede eliminar un gasto ya migrado a contabilidad.'))
        works = self.mapped('work_id')
        result = super().unlink()
        # Regenerar alertas tras eliminar gasto
        for work in works:
            self.env['building.alert.engine'].rebuild_alerts(work.id)
        return result
