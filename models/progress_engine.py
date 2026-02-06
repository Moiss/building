# -*- coding: utf-8 -*-
"""
TECH_NOTES.md
=============
PROGRESS ENGINE (MOTOR ÚNICO DE AVANCE)

Este módulo centraliza TODOS los cálculos de avance físico para el proyecto.
Reemplaza la lógica dispersa en `_compute` methods de los modelos individuales.

ESTRATEGIA:
-----------
1. Single Source of Truth: `building.progress.engine`
2. Snapshots: Los modelos (Line, Stage, Work) tienen campos `stored` que son
   actualizados EXCLUSIVAMENTE por este motor.
3. Persistencia: Se usa `building.budget.progress` como log de transacciones.

FÓRMULAS:
---------
1. PARTIDA (Line):
   progress = clamp(SUM(logs), 0, 100)
   
2. ETAPA (Stage):
   Promedio Ponderado por Importe (Planned Amount).
   Formula: SUM(line.progress * line.amount) / SUM(line.amount)
   * Si SUM(line.amount) == 0, se usa promedio simple.

3. PROYECTO (Work):
   Promedio Ponderado por Importe de Etapa (Suma de partidas).
   Formula: SUM(stage.progress * stage.total_amount) / SUM(stage.total_amount)
   * Si SUM(stage.total_amount) == 0, se usa promedio simple de etapas.

PUNTOS DE ENTRADA:
------------------
- apply_progress(): Registra un nuevo avance y dispara recálculo.
- recompute_hierarchy(): Recalcula toda la cadena (Line -> Stage -> Work).
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

class BuildingProgressEngine(models.AbstractModel):
    _name = 'building.progress.engine'
    _description = 'Motor de Cálculo de Avances'

    @api.model
    def apply_progress(self, project_id, stage_id, wbs_item_id, value_type='percent', value=0.0, date=None, user_id=None, note=None):
        """
        Registra un avance y dispara la actualización de snapshots.
        
        Args:
            project_id (int): ID de la obra (building.work)
            stage_id (int): ID de la etapa (building.work.stage)
            wbs_item_id (int): ID de la partida (building.budget.line)
            value (float): Valor del avance (si es percent, es el delta del periodo o acumulado?)
                           NOTA: El modelo actual usa 'percent_period' (delta).
            date (date): Fecha del avance.
        
        Returns:
            record: El registro creado en building.budget.progress
        """
        ProgressLog = self.env['building.budget.progress']
        
        # 1. Validaciones básicas
        if value_type != 'percent':
            raise NotImplementedError("Solo se soporta tipo 'percent' por ahora.")
            
        # 2. Crear registro
        log_vals = {
            'line_id': wbs_item_id,
            # stage_id y work_id son related en el modelo, no se escriben directo
            'date': date or fields.Date.context_today(self),
            'percent_period': value,
            'user_id': user_id or self.env.user.id,
            'notes': note,
            'state': 'confirmed', # Auto-confirmar al venir del engine
        }
        log = ProgressLog.create(log_vals)
        
        # 3. Disparar Recálculo Jerárquico
        # Pasamos los IDs afectados para optimizar, aunque el recompute suele ser cascada
        self.recompute_hierarchy(project_id, stage_ids=[stage_id], line_ids=[wbs_item_id])
        
        return log

    @api.model
    def recompute_hierarchy(self, work_id, stage_ids=None, line_ids=None):
        """
        Recalcula los snapshots de Partidas -> Etapas -> Obra.
        Sigue el orden estricto de abajo hacia arriba.
        """
        # 1. Recalcular Partidas (Lines) afectadas
        if line_ids:
            lines = self.env['building.budget.line'].browse(line_ids)
            self._recompute_lines(lines)
        
        # 2. Recalcular Etapas (Stages) afectadas
        # Si no se pasaron stages explícitos, deducir de las líneas o recalcular todas de la obra
        if stage_ids:
            stages = self.env['building.work.stage'].browse(stage_ids)
        elif work_id:
            stages = self.env['building.work.stage'].search([('work_id', '=', work_id)])
        else:
            stages = self.env['building.work.stage'].browse([])
            
        if stages:
            self._recompute_stages(stages)
            
        # 3. Recalcular Obra (Work)
        if work_id:
            work = self.env['building.work'].browse(work_id)
            self._recompute_work(work)

    @api.model
    def _recompute_lines(self, lines):
        """
        Recalcula snapshot 'physical_progress' y 'executed_amount' para las partidas.
        Formula: Suma de logs confirmados, clamp 0-100.
        """
        for line in lines:
            # Obtener logs
            logs = self.env['building.budget.progress'].search([
                ('line_id', '=', line.id),
                ('state', '=', 'confirmed')
            ])
            
            # Sumar periodos
            total_progress = sum(logs.mapped('percent_period'))
            
            # Clamp 0-100
            final_progress = max(0.0, min(100.0, total_progress))
            
            # Calcular ejecutado
            executed = line.amount * (final_progress / 100.0)
            
            # Actualizar Snapshot (bypass readonly si es necesario, 
            # pero como es python code, write funciona aunque sea readonly en vista)
            line.write({
                'physical_progress': final_progress,
                'executed_amount': executed,
                # Actualizar metadata último avance
                'last_progress_date': logs and logs[0].date or False,
                'last_progress_user_id': logs and logs[0].user_id.id or False
            })

    @api.model
    def _recompute_stages(self, stages):
        """
        Recalcula snapshot 'progress_pct' para las etapas.
        Formula: Promedio Ponderado por Importe.
        """
        for stage in stages:
            lines = stage.budget_line_ids
            if not lines:
                # Fallback: Mantener compatibilidad con modo manual antiguo (Fase 3.2)
                # Si no tiene líneas, se basa en sus propios logs manuales heredados
                logs = stage.progress_ids.filtered(lambda r: r.state == 'confirmed')
                manual_progress = sum(logs.mapped('progress_pct')) if logs else 0.0
                stage.write({'progress_pct': max(0.0, min(100.0, manual_progress))})
                continue
                
            total_amount = sum(lines.mapped('amount'))
            
            if total_amount > 0:
                weighted_sum = sum(l.physical_progress * l.amount for l in lines)
                stage_progress = weighted_sum / total_amount
            else:
                # Promedio simple si importes son 0
                avg_sum = sum(lines.mapped('physical_progress'))
                stage_progress = avg_sum / len(lines) if len(lines) > 0 else 0.0
                
                stage_progress = avg_sum / len(lines) if len(lines) > 0 else 0.0
            
            # Obtener la fecha de último avance de las partidas
            # mapped puede devolver [False, date, False], hay que filtrar
            last_dates = [d for d in lines.mapped('last_progress_date') if d]
            last_date = max(last_dates) if last_dates else False
                
            stage.write({
                'progress_pct': stage_progress,
                'last_progress_date': last_date
            })

    @api.model
    def _recompute_work(self, work):
        """
        Recalcula snapshot 'overall_progress' para la obra.
        Formula: Promedio Ponderado de las Etapas.
        """
        stages = work.stage_ids
        if not stages:
            work.write({'overall_progress': 0.0})
            return

        # Calcular importe total de cada etapa (suma de sus partidas)
        # Esto podría ser un campo computado en stage, pero el engine lo calcula al vuelo
        # para asegurar integridad.
        
        stage_amounts = {}
        for stage in stages:
            stage_amounts[stage.id] = sum(stage.budget_line_ids.mapped('amount'))
            
        total_project_amount = sum(stage_amounts.values())
        
        if total_project_amount > 0:
            weighted_sum = 0.0
            for stage in stages:
                amount = stage_amounts[stage.id]
                weighted_sum += stage.progress_pct * amount
            
            work_progress = weighted_sum / total_project_amount
        else:
             # Promedio simple de etapas
            avg_sum = sum(stages.mapped('progress_pct'))
            work_progress = avg_sum / len(stages)
            
        work.write({'overall_progress': work_progress})
