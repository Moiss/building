# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class BuildingAlertEngine(models.AbstractModel):
    """
    Motor de Alertas (Alert Engine).
    Centraliza la lógica de generación y actualización de alertas de obra.
    """
    _name = 'building.alert.engine'
    _description = 'Motor de Alertas'

    @api.model
    def rebuild_alerts(self, work_id):
        """
        Reconstruye las alertas de la obra basándose en reglas operativas.
        Se debe llamar después de cualquier cambio significativo (avance, presupuesto, gastos).
        """
        work = self.env['building.work'].browse(work_id)
        if not work:
            return

        from datetime import timedelta
        AlertModel = self.env['building.work.alert']
        
        # Eliminar alertas automáticas existentes (las que tienen rule_code)
        # Usamos sudo() por si el usuario actual no tiene permisos de borrado,
        # aunque el sistema debería manejarlo.
        work.alert_ids.filtered(lambda a: a.rule_code).unlink()
        
        alerts_to_create = []
        
        # =====================================================
        # REGLA 1: PRESUPUESTO NO VALIDADO
        # Condición: Si el presupuesto no está en estado 'validated'
        # Severidad: Advertencia | Tipo: Planeación
        # =====================================================
        budget = work._get_active_budget()
        if budget and budget.state != 'validated':
            alerts_to_create.append({
                'work_id': work.id,
                'name': _('El presupuesto aún no está validado.'),
                'severity': 'warning',
                'alert_type': 'planning',
                'rule_code': 'RULE_01_BUDGET_NOT_VALIDATED',
                'is_active': True,
            })
        
        # =====================================================
        # REGLA 2: AVANCE FINANCIERO > AVANCE FÍSICO + TOLERANCIA
        # Condición: financial_progress > overall_progress + tolerancia
        # Severidad: Crítica | Tipo: Financiera
        # =====================================================
        # IMPORTANTE: Asegurarse de que los valores de work estén frescos
        # work.invalidate_recordset(['financial_progress', 'overall_progress']) 
        # (Opcional, pero recomendable si venimos de un write reciente)
        
        tolerance = work.financial_tolerance or 5.0
        if work.financial_progress > (work.overall_progress + tolerance):
            alerts_to_create.append({
                'work_id': work.id,
                'name': _('El gasto va más rápido que el avance físico. (Financiero: %.1f%% vs Físico: %.1f%%)') % (
                    work.financial_progress, work.overall_progress
                ),
                'severity': 'critical',
                'alert_type': 'financial',
                'rule_code': 'RULE_02_FINANCIAL_EXCEEDS_PHYSICAL',
                'is_active': True,
            })
        
        # =====================================================
        # REGLA 3: ETAPA ACTIVA SIN AVANCE
        # Condición: Etapa en 'in_progress' sin avance en X días
        # Severidad: Advertencia | Tipo: Operativa
        # =====================================================
        days_limit = work.days_without_progress or 7
        threshold_datetime = fields.Datetime.now() - timedelta(days=days_limit)
        
        for stage in work.stage_ids.filtered(lambda s: s.state == 'in_progress'):
            # Si tiene avance, revisar fecha del último avance
            if stage.last_progress_date:
                if stage.last_progress_date < threshold_datetime:
                   alerts_to_create.append({
                        'work_id': work.id,
                        'name': _('La etapa "%s" no tiene avances registrados en los últimos %d días.') % (
                            stage.name, days_limit
                        ),
                        'severity': 'warning',
                        'alert_type': 'operational',
                        'rule_code': 'RULE_03_NO_PROGRESS_%d' % stage.id,
                        'is_active': True,
                    })
            else:
                # Si NO tiene avance, verificar tiempo desde el inicio de la etapa (holgura inicial)
                # Si no tiene date_start, usamos write_date (fecha de cambio de estado aprox)
                reference_date = stage.date_start or stage.write_date
                # Convertir a datetime si es date
                if reference_date:
                     # Asegurar compatibilidad de tipos (datetime vs date)
                    ref_dt = fields.Datetime.to_datetime(reference_date)
                    if ref_dt < threshold_datetime:
                        alerts_to_create.append({
                            'work_id': work.id,
                            'name': _('La etapa "%s" inició hace más de %d días y aún no registra avances.') % (
                                stage.name, days_limit
                            ),
                            'severity': 'warning',
                            'alert_type': 'operational',
                            'rule_code': 'RULE_03_NO_START_PROGRESS_%d' % stage.id,
                            'is_active': True,
                        })
        
        # =====================================================
        # REGLA 4: ETAPA RETRASADA VS PLANEACIÓN
        # Condición: avance_real < avance_esperado según fechas
        # Severidad: Advertencia | Tipo: Operativa
        # =====================================================
        for stage in work.stage_ids.filtered(lambda s: s.state == 'in_progress'):
            # Solo si tiene fechas planeadas y el avance real es menor al esperado
            if stage.planned_progress > 0 and stage.progress_pct < (stage.planned_progress - 10):
                alerts_to_create.append({
                    'work_id': work.id,
                    'name': _('La etapa "%s" presenta retraso respecto a la planeación. (Real: %.1f%% vs Esperado: %.1f%%)') % (
                        stage.name, stage.progress_pct, stage.planned_progress
                    ),
                    'severity': 'warning',
                    'alert_type': 'operational',
                    'rule_code': 'RULE_04_STAGE_DELAYED_%d' % stage.id,
                    'is_active': True,
                })
        
        # =====================================================
        # REGLA 5: ANTICIPOS PLANEADOS > ANTICIPO DEL CLIENTE
        # Condición: suma_anticipos_partidas > anticipo_cliente_planeado
        # Severidad: Informativa | Tipo: Liquidez
        # =====================================================
        if budget and work.client_advance_planned > 0:
            total_advances = sum(budget.chapter_ids.mapped('total_advance'))
            if total_advances > work.client_advance_planned:
                alerts_to_create.append({
                    'work_id': work.id,
                    'name': _('Los anticipos planeados ($%.2f) superan el anticipo del cliente ($%.2f).') % (
                        total_advances, work.client_advance_planned
                    ),
                    'severity': 'info',
                    'alert_type': 'liquidity',
                    'rule_code': 'RULE_05_ADVANCES_EXCEED_CLIENT',
                    'is_active': True,
                })
        
        # =====================================================
        # REGLAS HEREDADAS (mantener compatibilidad)
        # =====================================================
        
        # Exceso sobre presupuesto (ya existía)
        if work.budget_total > 0:
            total_gastado = work.amount_committed + work.amount_paid
            if total_gastado > work.budget_total:
                alerts_to_create.append({
                    'work_id': work.id,
                    'name': _('Exceso sobre presupuesto: comprometido/pagado supera el total.'),
                    'severity': 'critical',
                    'alert_type': 'budget',
                    'rule_code': 'LEGACY_BUDGET_EXCEEDED',
                    'is_active': True,
                })
        
        # Etapas pendientes de aprobación (ya existía)
        stages_to_approve = work.stage_ids.filtered(lambda s: s.state == 'to_approve')
        if stages_to_approve:
            alerts_to_create.append({
                'work_id': work.id,
                'name': _('Etapas por aprobar: %d') % len(stages_to_approve),
                'severity': 'warning',
                'alert_type': 'approval',
                'rule_code': 'LEGACY_STAGES_TO_APPROVE',
                'is_active': True,
            })
        
        # Etapas vencidas (ya existía)
        overdue_stages = work.stage_ids.filtered(lambda s: s.is_overdue)
        if overdue_stages:
            alerts_to_create.append({
                'work_id': work.id,
                'name': _('Etapas vencidas: %d') % len(overdue_stages),
                'severity': 'critical',
                'alert_type': 'time',
                'rule_code': 'LEGACY_OVERDUE_STAGES',
                'is_active': True,
            })
        
        # Crear todas las alertas
        if alerts_to_create:
            AlertModel.create(alerts_to_create)
