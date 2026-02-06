# -*- coding: utf-8 -*-
"""
Wizard: Registro de Avance Físico (building.progress.wizard)
Wizard para registrar avances físicos en etapas de obra.

FASE 3.2: Avance Físico
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class BuildingProgressWizard(models.TransientModel):
    """
    Wizard para Registrar Avance Físico.
    Permite al usuario registrar el avance del periodo de manera formal.
    """
    _name = 'building.progress.wizard'
    _description = 'Wizard de Registro de Avance'

    # === CAMPOS ===
    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa',
        required=True,
        readonly=True
    )

    date = fields.Date(
        string='Fecha del Avance',
        required=True,
        default=fields.Date.context_today,
        help='Fecha en que se realizó el avance'
    )

    progress_pct = fields.Float(
        string='Avance del Periodo (%)',
        required=True,
        default=0.0,
        help='Porcentaje de avance del periodo (0-100). Este valor se SUMA al acumulado.'
    )

    notes = fields.Text(
        string='Observaciones',
        help='Detalles del avance registrado'
    )

    # === CAMPOS INFORMATIVOS ===
    stage_name = fields.Char(
        related='stage_id.name',
        string='Nombre de Etapa',
        readonly=True
    )

    current_progress = fields.Float(
        string='Avance Actual (%)',
        compute='_compute_current_progress',
        help='Avance acumulado actual de la etapa'
    )

    max_progress = fields.Float(
        string='Máximo Registrable (%)',
        compute='_compute_current_progress',
        help='Porcentaje máximo que puede registrarse (100 - actual)'
    )

    new_total = fields.Float(
        string='Nuevo Total (%)',
        compute='_compute_new_total',
        help='Avance acumulado después de este registro'
    )

    work_name = fields.Char(
        related='stage_id.work_id.name',
        string='Obra',
        readonly=True
    )

    # === MÉTODOS COMPUTE ===
    @api.depends('stage_id')
    def _compute_current_progress(self):
        """Calcula el avance actual y el máximo registrable."""
        for wizard in self:
            wizard.current_progress = wizard.stage_id.progress_pct or 0.0
            wizard.max_progress = max(0.0, 100.0 - wizard.current_progress)

    @api.depends('progress_pct', 'current_progress')
    def _compute_new_total(self):
        """Calcula el nuevo total después del registro."""
        for wizard in self:
            wizard.new_total = min(100.0, wizard.current_progress + wizard.progress_pct)

    # === VALIDACIONES ===
    @api.constrains('date')
    def _check_date_not_future(self):
        """Valida que la fecha no sea futura."""
        today = fields.Date.context_today(self)
        for wizard in self:
            if wizard.date and wizard.date > today:
                raise ValidationError(_(
                    'No se permite registrar avances con fecha futura. '
                    'Use hoy o una fecha pasada.'
                ))

    @api.constrains('progress_pct')
    def _check_progress_pct(self):
        """Valida el porcentaje de avance."""
        for wizard in self:
            if wizard.progress_pct < 0:
                raise ValidationError(_('El porcentaje de avance no puede ser negativo.'))
            if wizard.progress_pct > 100:
                raise ValidationError(_('El porcentaje de avance no puede exceder 100%.'))

    @api.onchange('progress_pct')
    def _onchange_progress_pct(self):
        """Advertencia si el total excederá 100%."""
        if self.progress_pct > self.max_progress:
            return {
                'warning': {
                    'title': _('Avance excede el límite'),
                    'message': _(
                        'El avance ingresado (%.1f%%) excede el máximo registrable (%.1f%%).\n'
                        'Se limitará automáticamente a 100%% en el acumulado.'
                    ) % (self.progress_pct, self.max_progress)
                }
            }

    def action_confirm(self):
        """Confirma el registro de avance."""
        self.ensure_one()
        
        # Validación: fecha no puede ser futura
        today = fields.Date.context_today(self)
        if self.date > today:
            raise UserError(_(
                'No se permite registrar avances con fecha futura. '
                'Use hoy o una fecha pasada.'
            ))
        
        # Validación: porcentaje mayor a 0
        if self.progress_pct <= 0:
            raise UserError(_('Debe ingresar un porcentaje de avance mayor a 0.'))
        
        # Verificar que la etapa esté en estado válido (solo En Proceso)
        if self.stage_id.state != 'in_progress':
            raise UserError(_('Solo se puede registrar avance en etapas En Proceso.'))
        
        # Ajustar si excede 100%
        effective_progress = self.progress_pct
        if self.current_progress + effective_progress > 100:
            effective_progress = 100 - self.current_progress
        
        # Crear el registro de avance
        self.env['building.stage.progress'].create({
            'stage_id': self.stage_id.id,
            'date': self.date,
            'progress_pct': effective_progress,
            'user_id': self.env.user.id,
            'notes': self.notes,
        })
        
        # Mostrar notificación de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Avance Registrado'),
                'message': _(
                    'Se registró un avance de %.1f%% en la etapa "%s".\n'
                    'Nuevo avance total: %.1f%%'
                ) % (effective_progress, self.stage_id.name, self.stage_id.progress_pct + effective_progress),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_cancel(self):
        """Cancela el wizard."""
        return {'type': 'ir.actions.act_window_close'}
