# -*- coding: utf-8 -*-
"""
Modelo: Valor por Periodo (building.budget.period.value)
Almacena el monto distribuido para cada periodo (M1, M2, ...).
"""

from odoo import models, fields, api


class BuildingBudgetPeriodValue(models.Model):
    """
    Valor por Periodo.
    Representa el monto asignado a un periodo específico de una partida.
    """
    _name = 'building.budget.period.value'
    _description = 'Valor por Periodo de Presupuesto'
    _order = 'line_id, period_number'

    # === CAMPOS BÁSICOS ===
    line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        required=True,
        ondelete='cascade',
        index=True
    )

    period_number = fields.Integer(
        string='# Periodo',
        required=True,
        default=1,
        help='Número del periodo (1, 2, 3...)'
    )

    amount = fields.Float(
        string='Monto',
        default=0.0,
        help='Monto asignado a este periodo'
    )

    # === CAMPOS COMPUTADOS ===
    period_name = fields.Char(
        string='Periodo',
        compute='_compute_period_name',
        store=True,
        help='Nombre del periodo (M1, M2...)'
    )

    # === CAMPOS RELACIONADOS ===
    chapter_id = fields.Many2one(
        related='line_id.chapter_id',
        store=True,
        readonly=True
    )

    budget_id = fields.Many2one(
        related='line_id.budget_id',
        store=True,
        readonly=True
    )

    line_name = fields.Char(
        related='line_id.name',
        string='Concepto',
        readonly=True
    )

    line_code = fields.Char(
        related='line_id.code',
        string='Código',
        readonly=True
    )

    # === MÉTODOS COMPUTE ===
    @api.depends('period_number')
    def _compute_period_name(self):
        """Genera nombre del periodo: M1, M2, M3..."""
        for record in self:
            record.period_name = f"M{record.period_number}" if record.period_number else ""

    # === DISPLAY NAME ===
    def _compute_display_name(self):
        """Genera nombre para mostrar."""
        for record in self:
            record.display_name = f"{record.line_id.name} - {record.period_name}"

    # === ACCIONES ===
    def action_redistribute(self):
        """Redistribuye los montos de la partida y recarga el popup."""
        if self:
            line = self[0].line_id
            if line:
                line.action_distribute_uniform()
                # Retornar acción para recargar la vista
                return {
                    'type': 'ir.actions.act_window',
                    'name': f'Distribución: {line.name}',
                    'res_model': 'building.budget.period.value',
                    'view_mode': 'list',
                    'domain': [('line_id', '=', line.id)],
                    'context': {'default_line_id': line.id},
                    'target': 'new',
                }
        return True

    # === SINCRONIZACIÓN CON OBRA ===
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para forzar recálculo de KPIs en building.work."""
        records = super().create(vals_list)
        # Forzar recálculo de KPIs en la obra
        works = records.mapped('line_id.work_id')
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
        return records

    def write(self, vals):
        """Override write para forzar recálculo de KPIs en building.work."""
        result = super().write(vals)
        # Forzar recálculo de KPIs en la obra
        works = self.mapped('line_id.work_id')
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
        return result

    def unlink(self):
        """Override unlink para forzar recálculo de KPIs en building.work."""
        works = self.mapped('line_id.work_id')
        result = super().unlink()
        # Forzar recálculo después de eliminar
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
        return result
