# -*- coding: utf-8 -*-
"""
Wizard: Registrar Avance Físico por Partida
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BuildingBudgetProgressWizard(models.TransientModel):
    """
    Wizard para registrar avance físico a una partida.
    """
    _name = 'building.budget.progress.wizard'
    _description = 'Registrar Avance por Partida'

    line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        required=True,
        readonly=True
    )
    
    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa',
        compute='_compute_stage_id',
        store=True,
        readonly=False,
        # No required=True aquí: la validación se hace en action_confirm()
        # porque el campo es computed y puede quedar vacío inicialmente
        help='Etapa asignada a esta partida. Si no tiene, debe asignarla para registrar avance.'
    )

    is_stage_editable = fields.Boolean(
        compute='_compute_stage_id',
        store=True
    )
    
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today
    )
    
    current_accumulated = fields.Float(
        string='Acumulado Actual (%)',
        readonly=True
    )
    
    percent_period = fields.Float(
        string='Avance a Registrar (%)',
        required=True,
        default=0.0
    )
    
    max_registrable = fields.Float(
        string='Máximo Registrable (%)',
        compute='_compute_max_registrable',
        help='Porcentaje restante para llegar al 100%'
    )
    
    notes = fields.Text(
        string='Notas / Evidencia',
        required=True,
        help='Describa el avance realizado'
    )

    @api.depends('line_id')
    def _compute_stage_id(self):
        for wizard in self:
            if wizard.line_id and wizard.line_id.stage_id:
                wizard.stage_id = wizard.line_id.stage_id
                wizard.is_stage_editable = False
            else:
                # Si no tiene etapa, permitir edición (no asignar nada por defecto si queremos obligar a elegir)
                # O podríamos pre-llenar si hay lógica, pero mejor dejar limpio para forzar elección
                wizard.stage_id = False
                wizard.is_stage_editable = True

    @api.depends('current_accumulated')
    def _compute_max_registrable(self):
        for wizard in self:
            # Asegurar escala 0-100
            current = wizard.current_accumulated or 0.0
            wizard.max_registrable = max(0.0, 100.0 - current)

    @api.constrains('percent_period')
    def _check_percent_limit(self):
        for wizard in self:
            if wizard.percent_period <= 0:
                raise ValidationError(_('El avance debe ser mayor a 0.'))
            if wizard.percent_period > 100:
                raise ValidationError(_('El avance no puede ser mayor al 100%.'))
                
            # Validar contra máximo registrable (con tolerancia flotante)
            if wizard.percent_period > (wizard.max_registrable + 0.01):
                 raise ValidationError(_(
                    'No puede registrar más del %.2f%% restante.\n'
                    'Acumulado actual: %.2f%%'
                 ) % (wizard.max_registrable, wizard.current_accumulated))
    
    @api.constrains('date')
    def _check_future_date(self):
        """No permite registrar avances con fecha futura."""
        today = fields.Date.context_today(self)
        for wizard in self:
            if wizard.date and wizard.date > today:
                raise ValidationError(_('No se pueden registrar avances con fecha futura.'))

    def action_confirm(self):
        """Crea el registro de registro y asigna etapa si faltaba."""
        self.ensure_one()
        
        # 1. Asignar etapa si no la tenía
        if self.line_id and not self.line_id.stage_id:
            if not self.stage_id:
                raise ValidationError(_('Debe seleccionar una Etapa para continuar.'))
            self.line_id.write({'stage_id': self.stage_id.id})
            
        # 1.5 Validar estado de la etapa (solo permitir en proceso)
        stage = self.line_id.stage_id
        if stage and stage.state != 'in_progress':
             raise ValidationError(_(
                 'Solo se pueden registrar avances en etapas "En Proceso".\n'
                 'La etapa actual "%s" está en estado "%s".'
             ) % (stage.name, dict(stage._fields['state'].selection).get(stage.state)))
        
        # 2. Delegar al Motor Único
        self.env['building.progress.engine'].apply_progress(
            project_id=self.line_id.work_id.id,
            stage_id=self.line_id.stage_id.id,
            wbs_item_id=self.line_id.id,
            value_type='percent',
            value=self.percent_period,
            date=self.date,
            user_id=self.env.user.id,
            note=self.notes
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
