# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo import fields

@tagged('post_install', '-at_install', 'progress_engine')
class TestProgressEngine(TransactionCase):

    def setUp(self):
        super(TestProgressEngine, self).setUp()
        
        # 1. Crear Obra
        self.work = self.env['building.work'].create({
            'name': 'Engine Test Work',
            'budget_total': 10000.0 # Will be computed, but init helper
        })
        
        # 2. Crear Etapas
        self.stage_1 = self.env['building.work.stage'].create({
            'name': 'Stage 1',
            'work_id': self.work.id,
            'state': 'in_progress'
        })
        self.stage_2 = self.env['building.work.stage'].create({
            'name': 'Stage 2',
            'work_id': self.work.id,
            'state': 'planning'
        })
        
        # 3. Crear Presupuesto y Capítulos
        self.budget = self.env['building.budget'].create({
            'name': 'Budget Test',
            'work_id': self.work.id
        })
        self.chapter = self.env['building.budget.chapter'].create({
            'name': 'Chapter 1',
            'budget_id': self.budget.id,
            'code': '01'
        })
        
        # 4. Crear Partidas (Lines)
        # Line 1: 1000 @ Stage 1
        self.line_1 = self.env['building.budget.line'].create({
            'name': 'Line 1',
            'chapter_id': self.chapter.id,
            'code': '01.01',
            'amount': 1000.0,
            'stage_id': self.stage_1.id
        })
        
        # Line 2: 3000 @ Stage 1
        self.line_2 = self.env['building.budget.line'].create({
            'name': 'Line 2',
            'chapter_id': self.chapter.id,
            'code': '01.02',
            'amount': 3000.0,
            'stage_id': self.stage_1.id
        })
        
        # Line 3: 4000 @ Stage 2
        self.line_3 = self.env['building.budget.line'].create({
            'name': 'Line 3',
            'chapter_id': self.chapter.id,
            'code': '01.03',
            'amount': 4000.0,
            'stage_id': self.stage_2.id
        })
        
        # Line 4: 2000 @ No Stage (Should not crash engine)
        self.line_4 = self.env['building.budget.line'].create({
            'name': 'Line 4',
            'chapter_id': self.chapter.id,
            'code': '01.04',
            'amount': 2000.0
        })

    def test_01_apply_progress_and_weights(self):
        """Probar aplicación de avance y cálculo ponderado."""
        engine = self.env['building.progress.engine']
        
        # Apply 50% to Line 1 ($1000)
        engine.apply_progress(
            project_id=self.work.id,
            stage_id=self.stage_1.id,
            wbs_item_id=self.line_1.id,
            value_type='percent',
            value=50.0,
            date=fields.Date.today()
        )
        
        # Verify Line 1 Snapshot
        self.assertEqual(self.line_1.physical_progress, 50.0)
        self.assertEqual(self.line_1.executed_amount, 500.0)
        
        # Verify Stage 1 Weighted Average
        # Stage 1 Total: 1000 + 3000 = 4000
        # Weighted: (1000 * 0.5) + (3000 * 0.0) = 500
        # Pct: 500 / 4000 = 0.125 (12.5%)
        # Need to refresh record?
        self.stage_1.invalidate_recordset()
        self.assertAlmostEqual(self.stage_1.progress_pct, 12.5, places=2)
        
        # Verify Work Weighted Average
        # Project Total (assigned to stages + unassigned? Formula uses stage items)
        # Wait, formula says: sum(stage.progress * stage.total_amount)
        # Stage 1 Amt: 4000, Prog: 12.5% -> Executed: 500
        # Stage 2 Amt: 4000, Prog: 0% -> Executed: 0
        # Total Stages Amt: 8000 (Line 4 is orphan, Engine logic ignores it or no?)
        # Let's check engine logic: sum(stage_amounts.values()) iterates over stages on work.
        # So only Line 1, 2, 3 count (8000). Line 4 is ignored for Overall Progress.
        # Valid behavior for "Work Progress based on Stages".
        # Calc: 500 / 8000 = 0.0625 (6.25%)
        
        self.work.invalidate_recordset()
        self.assertAlmostEqual(self.work.overall_progress, 6.25, places=2)

    def test_02_clamp_constraints(self):
        """Probar validaciones de rango (0-100%)."""
        engine = self.env['building.progress.engine']
        from odoo.exceptions import ValidationError
        
        # Test: > 100% raises ValidationError
        with self.assertRaises(ValidationError):
            engine.apply_progress(
                self.work.id, self.stage_1.id, self.line_2.id,
                value=150.0
            )
        
        # Test: < 0% raises ValidationError
        with self.assertRaises(ValidationError):
            engine.apply_progress(
                self.work.id, self.stage_1.id, self.line_2.id,
                value=-10.0
            )

    def test_03_recompute_on_amount_change(self):
        """Probar recálculo al cambiar importes."""
        engine = self.env['building.progress.engine']
        
        # Setup: Line 1 (1000) at 100%, Line 2 (3000) at 0%
        # Stage 1 Avg: (1000*1 + 0) / 4000 = 25%
        engine.apply_progress(self.work.id, self.stage_1.id, self.line_1.id, value=100.0)
        self.assertAlmostEqual(self.stage_1.progress_pct, 25.0)
        
        # Change Line 1 amount to 9000
        # New Stage Total: 9000 + 3000 = 12000
        # New Weighted: (9000*1 + 0) = 9000
        # New Avg: 9000 / 12000 = 0.75 (75%)
        self.line_1.write({'amount': 9000.0})
        
        # Check if write triggered recompute
        self.stage_1.invalidate_recordset()
        self.assertAlmostEqual(self.stage_1.progress_pct, 75.0)

    def test_04_date_propagation_and_alerts(self):
        """Probar propagación de fechas y generación de alertas."""
        engine = self.env['building.progress.engine']
        alert_engine = self.env['building.alert.engine']
        from datetime import timedelta
        
        # 1. Propagación de Fechas
        date_1 = fields.Date.today() - timedelta(days=5)
        engine.apply_progress(
            self.work.id, self.stage_1.id, self.line_1.id, 
            value=10.0, date=date_1
        )
        self.stage_1.invalidate_recordset()
        # Verificar que la fecha subió a la etapa
        # last_progress_date es Datetime, date_1 es Date. Odoo maneja la conv.
        self.assertTrue(self.stage_1.last_progress_date)
        self.assertEqual(self.stage_1.last_progress_date.date(), date_1)
        
        # 2. Nueva fecha más reciente
        date_2 = fields.Date.today()
        engine.apply_progress(
            self.work.id, self.stage_1.id, self.line_2.id, 
            value=10.0, date=date_2
        )
        self.stage_1.invalidate_recordset()
        self.assertEqual(self.stage_1.last_progress_date.date(), date_2)

        # 3. Test Alerta: Sin avance al inicio
        # Configurar etapa nueva sin avances
        self.stage_2.write({
            'state': 'in_progress',
            'date_start': fields.Date.today() - timedelta(days=10),
            'last_progress_date': False # Limpiar por si acaso
        })
        
        # Ejecutar motor de alertas
        alert_engine.rebuild_alerts(self.work.id)
        
        # Buscar alerta "NO START PROGRESS" (inició hace > 7 días y sin avance)
        alerts = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('rule_code', 'like', 'RULE_03_NO_START_PROGRESS%')
        ])
        self.assertTrue(alerts, "Debe generar alerta por no iniciar avances")
        
        # 4. Test Alerta: Avance antiguo
        # Simular que tuvo avance hace 8 días
        date_old = fields.Date.today() - timedelta(days=8)
        engine.apply_progress(
            self.work.id, self.stage_2.id, self.line_3.id, 
            value=10.0, date=date_old
        )
        
        alert_engine.rebuild_alerts(self.work.id)
        
        # Buscar alerta "NO PROGRESS" (sin avance en ultimos 7 días)
        alerts_stalled = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('rule_code', 'like', 'RULE_03_NO_PROGRESS%')
        ])
        self.assertTrue(alerts_stalled, "Debe generar alerta por avance estancado")
        
        # 5. Test Alerta: Avance reciente (Limpiar alertas)
        engine.apply_progress(
            self.work.id, self.stage_2.id, self.line_3.id, 
            value=5.0, date=fields.Date.today()
        )
        alert_engine.rebuild_alerts(self.work.id)
        
        alerts_clean = self.env['building.work.alert'].search([
            ('work_id', '=', self.work.id),
            ('rule_code', 'like', 'RULE_03%')
        ])
        # Filtrar solo para stage_2
        alerts_stage_2 = alerts_clean.filtered(lambda a: str(self.stage_2.id) in a.rule_code)
        self.assertFalse(alerts_stage_2, "No debe haber alertas si hay avance reciente")
