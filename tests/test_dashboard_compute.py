# -*- coding: utf-8 -*-
"""
Test: Cálculos del Dashboard
Verifica que los campos computados funcionen correctamente.
"""

from odoo.tests import TransactionCase, tagged
from odoo.tools import float_compare

@tagged('post_install', '-at_install', 'building_dashboard')
class TestDashboardCompute(TransactionCase):
    """Tests para campos computados del dashboard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Crear obra de prueba
        cls.work = cls.env['building.work'].create({
            'name': 'Obra Test Compute',
        })
        
        # Crear presupuesto y validarlo para tener KPIs financieros
        cls.budget = cls.env['building.budget'].create({
            'name': 'Presupuesto Test',
            'work_id': cls.work.id,
            'duration_months': 12,
        })
        
        cls.chapter = cls.env['building.budget.chapter'].create({
            'name': 'Capítulo 1',
            'budget_id': cls.budget.id,
        })
        
        # Crear partida con importe 1000
        cls.line = cls.env['building.budget.line'].create({
            'name': 'Partida 1',
            'code': '1',
            'chapter_id': cls.chapter.id,
            'budget_id': cls.budget.id,
            'amount': 1000.0,
        })
        
        # Distribuir para tener comprometido
        # Distribuir 500 en periodo 1 y 500 en periodo 2 (simulado)
        # Por defecto la partida no tiene distribución manual, usar la automatica
        cls.line.action_distribute_uniform()
        
        # Validar presupuesto
        cls.budget.action_validate()
        
        # work.budget_total debería ser 1000.0
        # work.amount_committed debería ser 1000.0 (porque se distribuyó todo)

    def test_01_budget_kpis_compute(self):
        """Verifica que budget_total y amount_committed se calculan tras validar presupuesto."""
        self.assertEqual(self.work.budget_total, 1000.0)
        self.assertEqual(self.work.amount_committed, 1000.0)

    def test_02_amount_available_compute(self):
        """Verifica cálculo de amount_available."""
        # amount_available = budget_total - amount_committed - amount_paid
        # Inicialmente: 1000 - 1000 - 0 = 0
        self.assertEqual(self.work.amount_available, 0.0)
        
        # Forzar un cambio en amount_paid (aunque sea 0)
        self.work.write({'amount_paid': 200.0})
        # 1000 - 1000 - 200 = -200 -> max(0, -200) = 0
        self.assertEqual(self.work.amount_available, 0.0)
        
        # Si reducimos lo comprometido (editando presupuesto borrador? no se puede editar validado)
        # Vamos a crear otro presupuesto borrador para simular más presupuesto disponible?
        # No, el active budget es el validado.
        
        # Para probar available > 0, necesitamos que total > committed.
        # Pero budget_total == total_amount y committed == total_distributed.
        # Si está validado, se supone que distributed == total (o casi).
        # Si hubiera diferencia (has_warning), entonces committed < total.
        pass

    def test_03_stage_count(self):
        """Verifica conteo de etapas."""
        self.assertEqual(self.work.stage_count, 0)
        
        self.env['building.work.stage'].create({
            'name': 'Etapa 1',
            'work_id': self.work.id,
        })
        
        self.assertEqual(self.work.stage_count, 1)

    def test_04_active_alert_count(self):
        """Verifica conteo de alertas activas."""
        # Limpiar alertas generadas en setup (e.g. consistencia)
        self.work.alert_ids.unlink()
        
        self.assertEqual(self.work.active_alert_count, 0)
        
        self.env['building.work.alert'].create({
            'name': 'Alerta Activa',
            'work_id': self.work.id,
            'severity': 'warning',
            'is_active': True,
        })
        self.env['building.work.alert'].create({
            'name': 'Alerta Inactiva',
            'work_id': self.work.id,
            'severity': 'info',
            'is_active': False,
        })
        
        self.assertEqual(self.work.active_alert_count, 1)

    def test_05_progress_avg(self):
        """Verifica cálculo de avance promedio."""
        stage1 = self.env['building.work.stage'].create({
            'name': 'Etapa 1',
            'work_id': self.work.id,
            'state': 'in_progress',
        })
        stage2 = self.env['building.work.stage'].create({
            'name': 'Etapa 2',
            'work_id': self.work.id,
            'state': 'in_progress',
        })
        
        # Registrar avance en etapa 1 (100%)
        self.env['building.stage.progress'].create({
            'stage_id': stage1.id,
            'progress_pct': 100.0,
            'state': 'confirmed',
        })
        # Registrar avance en etapa 2 (50%)
        self.env['building.stage.progress'].create({
            'stage_id': stage2.id,
            'progress_pct': 50.0,
            'state': 'confirmed',
        })
        
        # Trigger compute
        stage1.invalidate_recordset()
        stage2.invalidate_recordset()
        self.work.invalidate_recordset()
        
        # Promedio: (100 + 50) / 2 = 75
        self.assertEqual(self.work.progress_avg, 75.0)

    def test_06_rebuild_alerts_budget_exceeded(self):
        """Verifica generación de alerta por exceso de presupuesto."""
        # Presupuesto total: 1000
        # Comprometido: 1000
        # Pagado: 0
        # Total gastado = 1000 == 1000 (No excede)
        
        # Simular pago de 100 para exceder (1100 > 1000)
        self.work.write({'amount_paid': 100.0})
        
        # Forzar regeneración de alertas
        self.work._rebuild_alerts()
        
        alert = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('alert_type', '=', 'budget'),
            ('is_active', '=', True),
        ])
        
        self.assertTrue(alert, "Debe existir una alerta de presupuesto excedido")
        self.assertEqual(alert.severity, 'critical')

    def test_07_rebuild_alerts_stages_to_approve(self):
        """Verifica generación de alerta por etapas pendientes."""
        self.work.alert_ids.unlink()
        
        self.env['building.work.stage'].create({
            'name': 'Etapa Por Aprobar',
            'work_id': self.work.id,
            'state': 'to_approve',
        })
        
        self.work._rebuild_alerts()
        
        alert = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('alert_type', '=', 'approval'),
            ('is_active', '=', True),
        ])
        
        self.assertTrue(alert, "Debe existir alerta de aprobación pendiente")

    def test_08_overall_progress_compute(self):
        """Verifica cálculo de avance global (overall_progress)."""
        # Ya tenemos stages del test_05? No, cada test corre aislado? 
        # No, TransactionCase mantiene datos si se crean en setUpClass. 
        # Pero los creados en test methods se revierten (update: TransactionCase rolls back after each test).
        # Asi que estamos limpios de stages creados en test_05.
        
        stage1 = self.env['building.work.stage'].create({
            'name': 'Etapa 1',
            'work_id': self.work.id,
            'state': 'in_progress',
        })
        
        self.env['building.stage.progress'].create({
            'stage_id': stage1.id,
            'progress_pct': 80.0,
            'state': 'confirmed',
        })
        
        stage1.invalidate_recordset()
        self.work.invalidate_recordset()
        
        self.assertEqual(self.work.overall_progress, 80.0)

    def test_09_financial_progress_compute(self):
        """Verifica cálculo de avance financiero."""
        # Budget Total: 1000
        # Committed: 1000
        # Paid: 0 (default setup)
        # Financial Progress = (0 + 1000) / 1000 * 100 = 100%
        
        self.assertEqual(self.work.financial_progress, 100.0)
        
        # Simular pago parcial
        self.work.write({'amount_paid': 500.0})
        # Financial Progress = (500 + 1000) / 1000 * 100 = 150% (excede presupuesto)
        self.assertEqual(self.work.financial_progress, 150.0)

    def test_10_consistency_warning(self):
        """Verifica detección de inconsistencia (financiero > físico)."""
        # Financial Setup: 100% (test_09 check)
        # Physical Setup: 0% (sin etapas con avance)
        
        # 100 > 0 -> Warning True
        self.assertTrue(self.work.consistency_warning)
        
        # Agregar etapa con avance 100
        stage = self.env['building.work.stage'].create({
            'name': 'Etapa 100',
            'work_id': self.work.id,
        })
        self.env['building.stage.progress'].create({
            'stage_id': stage.id,
            'progress_pct': 100.0,
            'state': 'confirmed',
        })
        self.work._compute_overall_progress() # Force recompute
        self.work._compute_consistency_warning()
        
        # Physical: 100, Financial: 100 -> No warning
        self.assertFalse(self.work.consistency_warning)

    def test_11_consistency_alert_generation(self):
        """Verifica generación de alerta de consistencia."""
        # Financial: 100%
        # Physical: 0%
        # Diff: 100 > 5 (tolerance) -> Critical Alert
        
        self.work._rebuild_alerts()
        
        alert = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('alert_type', '=', 'financial'), # Actualizado según código
            ('is_active', '=', True),
        ])
        
        self.assertTrue(alert, "Debe existir alerta de consistencia (financiera)")
        self.assertEqual(alert.severity, 'critical')

    def test_12_alert_emoji(self):
        """Verifica campo emoji en alertas."""
        alert_critical = self.env['building.work.alert'].create({
            'name': 'Test Crítico',
            'work_id': self.work.id,
            'severity': 'critical',
        })
        self.assertEqual(alert_critical.alert_emoji, '🔴')
