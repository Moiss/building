# -*- coding: utf-8 -*-
"""
Modelo: Historial de Avance por Partida (building.budget.progress)
Registra el avance físico detallado por concepto/partida.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BuildingBudgetProgress(models.Model):
    """
    Registro de Avance Físico por Partida.
    Historial inmutable (solo cancelable) de avances.
    """
    _name = 'building.budget.progress'
    _description = 'Avance Físico por Partida'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # === CAMPOS PRINCIPALES ===
    line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    stage_id = fields.Many2one(
        related='line_id.stage_id',
        store=True,
        readonly=True,
        index=True
    )
    
    work_id = fields.Many2one(
        related='line_id.work_id',
        store=True,
        readonly=True,
        index=True
    )
    
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
        help='Fecha real del avance en obra'
    )
    
    percent_period = fields.Float(
        string='Avance Periodo (%)',
        required=True,
        help='Porcentaje de avance realizado en este periodo (0-100)'
    )
    
    percent_accumulated = fields.Float(
        string='Acumulado (%)',
        compute='_compute_accumulated',
        store=True,
        help='Avance total acumulado incluyendo este registro'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        default=lambda self: self.env.user
    )
    
    notes = fields.Text(
        string='Notas / Evidencia',
        help='Descripción del trabajo realizado'
    )
    
    state = fields.Selection([
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='confirmed', required=True)
    
    display_name = fields.Char(compute='_compute_display_name', store=True)

    # === CONSTRAINS ===
    @api.constrains('date')
    def _check_future_date(self):
        """No permite registrar avances con fecha futura."""
        today = fields.Date.context_today(self)
        for record in self:
            if record.date > today:
                raise ValidationError(_('No se pueden registrar avances con fecha futura.'))

    @api.constrains('percent_period')
    def _check_percent_valid(self):
        for record in self:
            if record.percent_period < 0 or record.percent_period > 100:
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))

    @api.constrains('line_id')
    def _check_stage_assigned(self):
        """Valida que la partida tenga etapa asignada antes de registrar avance."""
        for record in self:
            if not record.line_id.stage_id:
                raise ValidationError(_(
                    'La partida "%s" no tiene una Etapa asignada.\n'
                    'Asigne una etapa a la partida antes de registrar avance.'
                ) % record.line_id.display_name)

    @api.constrains('percent_accumulated')
    def _check_accumulated_limit(self):
        """El acumulado no puede exceder 100%."""
        for record in self:
            if record.state == 'confirmed' and record.percent_accumulated > 100.01: # Tolerancia flotante
                raise ValidationError(_(
                    'El avance acumulado no puede exceder el 100%.\n'
                    'Acumulado calculado: %.2f%%'
                ) % record.percent_accumulated)

    # === COMPUTED FIELDS ===
    @api.depends('line_id', 'date', 'state', 'percent_period')
    def _compute_accumulated(self):
        """Calcula el acumulado histórico hasta este registro."""
        for record in self:
            if record.state == 'cancelled':
                # Si está cancelado, mostramos lo que "habría sido" o 0?
                # Mejor 0 para no confundir, o el valor del registro anterior?
                # Regla: Cancelado no suma.
                record.percent_accumulated = 0.0
                continue

            # Buscar registros anteriores o iguales de la misma partida activos
            domain = [
                ('line_id', '=', record.line_id.id),
                ('state', '=', 'confirmed'),
                '|', ('date', '<', record.date),
                     '&', ('date', '=', record.date), ('id', '<=', record.id) 
                     # Nota: si es NewId, id es falso, cuidado.
                     # Al crear, compute corre antes de tener ID.
            ]
            
            # Si es new record (id es False o NewId), sumar todo lo guardado + este valor
            if not record.id:
                 previous = self.search([
                     ('line_id', '=', record.line_id.id),
                     ('state', '=', 'confirmed')
                 ])
                 total = sum(previous.mapped('percent_period')) + record.percent_period
            else:
                 previous = self.search(domain)
                 total = sum(previous.mapped('percent_period'))
            
            record.percent_accumulated = total

    @api.depends('line_id.code', 'date', 'percent_period')
    def _compute_display_name(self):
        for record in self:
            date_str = record.date or ''
            record.display_name = f"{date_str} (+{record.percent_period}%)"

    # === CRUD OVERRIDES ===
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Disparar Engine para recálculo jerárquico
        self._trigger_engine_update()
        return records

    def write(self, vals):
        if 'state' not in vals:
            # Bloquear edición de datos si ya está confirmado
            for record in self:
                if record.state == 'confirmed':
                    raise UserError(_('No se pueden editar registros confirmados. Use "Cancelar" en su lugar.'))
        
        res = super().write(vals)
        self._trigger_engine_update()
        return res

    def _trigger_engine_update(self):
        """Delega la actualización al Motor Único."""
        # Identificar qué obras/etapas/partidas tocaron
        lines = self.mapped('line_id')
        works = lines.mapped('work_id')
        # Optimización: llamar por obra
        for work in works:
            work_lines = lines.filtered(lambda l: l.work_id == work)
            self.env['building.progress.engine'].recompute_hierarchy(
                work.id, 
                line_ids=work_lines.ids
            )

    # === ACCIONES ===
    def action_cancel(self):
        """Cancela el avance (reversión)."""
        self._check_permission()
        self.write({'state': 'cancelled'})

    def _check_permission(self):
        """Solo Admin/Director pueden cancelar."""
        user = self.env.user
        if not (user.has_group('building_dashboard.group_building_director') or 
                user.has_group('building_dashboard.group_building_admin') or 
                user.has_group('base.group_system')):
            raise UserError(_('Solo el Director de Obra puede cancelar avances.'))
