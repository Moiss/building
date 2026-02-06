# -*- coding: utf-8 -*-
"""
Modelo: Registro de Avance Físico (building.stage.progress)
Almacena los registros históricos de avance por etapa.

FASE 3.2: Avance Físico
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BuildingStageProgress(models.Model):
    """
    Registro de Avance Físico.
    Cada registro representa un avance real ejecutado en obra.
    Los registros NO son editables una vez guardados (solo cancelables).
    """
    _name = 'building.stage.progress'
    _description = 'Registro de Avance Físico'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # === CAMPOS PRINCIPALES ===
    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa',
        required=True,
        ondelete='cascade',
        index=True
    )

    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
        help='Fecha del avance registrado'
    )

    progress_pct = fields.Float(
        string='Avance del Periodo (%)',
        required=True,
        default=0.0,
        help='Porcentaje de avance del periodo (0-100)'
    )

    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        default=lambda self: self.env.user,
        help='Usuario que registra el avance'
    )

    notes = fields.Text(
        string='Observaciones',
        help='Detalles del avance registrado'
    )

    # === CAMPOS RELACIONADOS ===
    work_id = fields.Many2one(
        related='stage_id.work_id',
        store=True,
        readonly=True
    )

    company_id = fields.Many2one(
        related='stage_id.company_id',
        store=True,
        readonly=True
    )

    # === CAMPOS COMPUTADOS ===
    cumulative_pct = fields.Float(
        string='Acumulado (%)',
        compute='_compute_cumulative',
        store=True,
        help='Porcentaje acumulado hasta este registro'
    )

    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    # === ESTADO ===
    state = fields.Selection([
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='confirmed', required=True)

    # === CONSTRAINS ===
    @api.constrains('progress_pct')
    def _check_progress_pct(self):
        """Valida que el porcentaje esté entre 0 y 100."""
        for record in self:
            if record.progress_pct < 0 or record.progress_pct > 100:
                raise ValidationError(_(
                    'El porcentaje de avance debe estar entre 0 y 100.'
                ))

    @api.constrains('progress_pct', 'stage_id', 'state')
    def _check_cumulative_limit(self):
        """Valida que el acumulado no exceda 100%."""
        for record in self:
            if record.state == 'confirmed':
                # Calcular suma de avances confirmados para esta etapa
                confirmed_records = self.search([
                    ('stage_id', '=', record.stage_id.id),
                    ('state', '=', 'confirmed'),
                ])
                total = sum(confirmed_records.mapped('progress_pct'))
                if total > 100:
                    raise ValidationError(_(
                        'El avance acumulado no puede exceder 100%%.\n'
                        'Acumulado actual: %.1f%%'
                    ) % total)

    # === MÉTODOS COMPUTE ===
    @api.depends('stage_id', 'date', 'state')
    def _compute_cumulative(self):
        """Calcula el porcentaje acumulado hasta este registro."""
        for record in self:
            if record.state == 'cancelled':
                record.cumulative_pct = 0
                continue
            
            # Obtener todos los registros confirmados de la etapa hasta esta fecha
            earlier_records = self.search([
                ('stage_id', '=', record.stage_id.id),
                ('state', '=', 'confirmed'),
                '|',
                ('date', '<', record.date),
                '&',
                ('date', '=', record.date),
                ('id', '<=', record.id),
            ])
            record.cumulative_pct = min(100.0, sum(earlier_records.mapped('progress_pct')))

    @api.depends('stage_id.name', 'date', 'progress_pct')
    def _compute_display_name(self):
        """Genera nombre para mostrar."""
        for record in self:
            if record.stage_id and record.date:
                record.display_name = f"{record.stage_id.name} - {record.date} (+{record.progress_pct:.1f}%)"
            else:
                record.display_name = _('Nuevo Avance')

    # === CRUD OVERRIDES ===
    @api.model_create_multi
    def create(self, vals_list):
        """Override create para validar, actualizar fecha de avance y regenerar alertas."""
        records = super().create(vals_list)
        
        # Actualizar last_progress_date en las etapas afectadas
        for record in records:
            if record.state == 'confirmed' and record.stage_id:
                record.stage_id.write({
                    'last_progress_date': fields.Datetime.now()
                })
        
        # 2. Forzar recálculo de jerarquía en building.progress.engine
        works = records.mapped('stage_id.work_id')
        for work in works:
            self.env['building.progress.engine'].recompute_hierarchy(work.id)

        # 3. Regenerar alertas de las obras afectadas (ahora con datos frescos)
        for work in works:
            self.env['building.alert.engine'].rebuild_alerts(work.id)
        
        return records

    def write(self, vals):
        """Bloquea edición de registros confirmados (excepto cancelación).
        
        Al cambiar estado, fuerza recálculo del avance de la etapa.
        """
        # Si solo está cambiando estado (cancelar/restaurar), permitir
        if set(vals.keys()) == {'state'}:
            # Guardar etapas afectadas ANTES del cambio
            stages = self.mapped('stage_id')
            works = stages.mapped('work_id')
            
            result = super().write(vals)
            
            # Forzar recálculo del avance de las etapas
            # Invalidar el cache para forzar recompute
            stages.invalidate_recordset(['progress_pct'])
            
            # Actualizar last_progress_date basándose solo en registros confirmados
            for stage in stages:
                confirmed_records = stage.progress_ids.filtered(
                    lambda r: r.state == 'confirmed'
                ).sorted('date', reverse=True)
                if confirmed_records:
                    stage.write({'last_progress_date': fields.Datetime.now()})
                else:
                    stage.write({'last_progress_date': False})
            
            # 2. Forzar recálculo del engine global
            for work in works:
                self.env['building.progress.engine'].recompute_hierarchy(work.id)

            # 3. Regenerar alertas (Engine)
            for work in works:
                self.env['building.alert.engine'].rebuild_alerts(work.id)
            
            return result
        
        # Para otros campos, bloquear si está confirmado
        for record in self:
            if record.state == 'confirmed':
                raise UserError(_(
                    'No se pueden modificar registros de avance confirmados.\n'
                    'Si hay un error, cancele el registro y cree uno nuevo.'
                ))
        
        return super().write(vals)

    def unlink(self):
        """Bloquea eliminación de registros confirmados."""
        for record in self:
            if record.state == 'confirmed':
                raise UserError(_(
                    'No se pueden eliminar registros de avance confirmados.\n'
                    'Utilice la opción de cancelar en su lugar.'
                ))
        return super().unlink()

    # === ACCIONES ===
    def action_cancel(self):
        """Cancela el registro de avance y recarga la vista."""
        self._check_cancel_permission()
        self.write({'state': 'cancelled'})
        
        # Forzar recarga de la vista para mostrar cambios
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def _check_cancel_permission(self):
        """Verifica permisos para cancelar/restaurar."""
        user = self.env.user
        has_permission = (
            user.has_group('building_dashboard.group_building_director') or
            user.has_group('building_dashboard.group_building_admin') or
            user.has_group('base.group_system')
        )
        if not has_permission:
            raise UserError(
                _('Solo el Director de Obra o Administrador pueden cancelar/restaurar registros de avance.')
            )

    def action_restore(self):
        """Restaura un registro de avance cancelado.
        
        Valida que el acumulado resultante no exceda 100%.
        """
        self._check_cancel_permission()
        
        for record in self:
            if record.state != 'cancelled':
                raise UserError(_('Solo se pueden restaurar registros cancelados.'))
            
            # Verificar que no exceda 100% al restaurar
            stage = record.stage_id
            current_total = stage.progress_pct
            if current_total + record.progress_pct > 100:
                raise UserError(_(
                    'No se puede restaurar este registro porque el avance acumulado '
                    'excedería 100%%.\n'
                    'Avance actual: %.1f%%\n'
                    'Registro a restaurar: %.1f%%'
                ) % (current_total, record.progress_pct))
        
        self.write({'state': 'confirmed'})
        
        # Forzar recarga de la vista para mostrar cambios
        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }
