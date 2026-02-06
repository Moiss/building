# -*- coding: utf-8 -*-
"""
Test: Avance por Partida (FASE 3.3)
Verifica el registro de avance por partida y el cálculo ponderado de etapa.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

@tagged('post_install', '-at_install', 'building_dashboard')
class TestBudgetProgress(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Obra
        cls.work = cls.env['building.work'].create({
            'name': 'Obra Test Phase 3.3',
        })
        
        # Etapas
        cls.stage1 = cls.env['building.work.stage'].create({
            'name': 'Cimentación',
            'work_id': cls.work.id,
            'state': 'in_progress',
        })
        
        # Presupuesto
        cls.budget = cls.env['building.budget'].create({
            'name': 'Presupuesto Test',
            'work_id': cls.work.id,
            'duration_months': 12,
        })
        cls.chapter = cls.env['building.budget.chapter'].create({
            'name': 'Cap 1',
            'budget_id': cls.budget.id,
        })
        
        # Partida 1: Importe 1000
        cls.line1 = cls.env['building.budget.line'].create({
            'name': 'Excavación',
            'code': '1.01',
            'chapter_id': cls.chapter.id,
            'amount': 1000.0,
            'stage_id': cls.stage1.id, # Asignada a etapa
        })
        
        # Partida 2: Importe 3000
        cls.line2 = cls.env['building.budget.line'].create({
            'name': 'Relleno',
            'code': '1.02',
            'chapter_id': cls.chapter.id,
            'amount': 3000.0,
            'stage_id': cls.stage1.id, # Asignada a etapa
        })
        
        cls.budget.action_validate()

    def test_01_weighted_progress(self):
        """Verifica el cálculo de avance ponderado en la etapa."""
        # Inicialmente 0%
        self.assertEqual(self.stage1.progress_pct, 0.0)
        
        # Registrar 50% en Partida 1 (Importe 1000)
        # 1000 * 0.5 = 500 avance valorizado
        Wizard = self.env['building.budget.progress.wizard']
        wiz = Wizard.create({
            'line_id': self.line1.id,
            'percent_period': 50.0,
            'notes': 'Avance 50%',
        })
        wiz.action_confirm() # This triggers recompute
        
        # Verificar avance en partida
        self.assertEqual(self.line1.physical_progress, 50.0)
        
        # Verificar avance en etapa
        # Total Amount: 1000 + 3000 = 4000
        # Weighted Progress: (1000 * 0.5) + (3000 * 0) = 500
        # Stage Progress: 500 / 4000 = 0.125 -> 12.5%
        
        # Force recompute just in case (though action_confirm handles it)
        self.stage1.invalidate_recordset(['progress_pct'])
        self.assertEqual(self.stage1.progress_pct, 12.5)
        
    def test_02_accumulated_logic(self):
        """Verifica acumulado y validaciones."""
        # Registrar 60% en Partida 2 (Importe 3000)
        self.env['building.budget.progress'].create({
            'line_id': self.line2.id,
            'percent_period': 60.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
        })
        
        self.assertEqual(self.line2.physical_progress, 60.0)
        
        # Intentar registrar 50% más (Total 110%) -> Debe fallar
        with self.assertRaises(ValidationError):
            self.env['building.budget.progress'].create({
                'line_id': self.line2.id,
                'percent_period': 50.0,
                'state': 'confirmed',
                'user_id': self.env.user.id,
            })

    def test_03_cancel_progress(self):
        """Verifica cancelación de avance."""
        """Verifica cancelación de avance."""
        # Limpiar avances previos si existen (ya que test_01 corre antes)
        self.line1.progress_ids.unlink()
        
        # Estado inicial limpio
        self.assertEqual(self.line1.physical_progress, 0.0)

        # Agregar 50%
        self.env['building.budget.progress'].create({
            'line_id': self.line1.id,
            'percent_period': 50.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
        })
        
        # Agregar 10% más
        prog = self.env['building.budget.progress'].create({
            'line_id': self.line1.id,
            'percent_period': 10.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
        })
        
        self.assertEqual(self.line1.physical_progress, 60.0) # 50 + 10
        
        # Cancelar el de 10%
        prog.action_cancel()
        
        self.assertEqual(self.line1.physical_progress, 50.0) # Vuelve a 50
        
        # Verificar impacto en etapa
        # (1000 * 0.5) / 4000 = 12.5%
        self.stage1.invalidate_recordset(['progress_pct'])
        self.assertEqual(self.stage1.progress_pct, 12.5)

    def test_04_fallback_logic(self):
        """Verifica que si no hay partidas, usa lógica manual (3.2)."""
        stage_manual = self.env['building.work.stage'].create({
            'name': 'Etapa Manual',
            'work_id': self.work.id,
            'state': 'in_progress',
        })
        
        # No tiene partidas asignadas. Registrar avance manual (3.2)
        self.env['building.stage.progress'].create({
            'stage_id': stage_manual.id,
            'progress_pct': 30.0,
            'state': 'confirmed',
        })
        
        self.assertEqual(stage_manual.progress_pct, 30.0)
        
        # Ahora asignarle una partida (Debemos reabrir presupuesto)
        self.budget.sudo().action_set_draft()
        
        line3 = self.env['building.budget.line'].create({
            'name': 'Partida Nueva',
            'code': '1.09',
            'chapter_id': self.chapter.id,
            'amount': 1000.0,
            'stage_id': stage_manual.id,
        })
        
        # Validar de nuevo
        self.budget.action_validate()
        
        # Al tener partida (avance 0%), el avance de etapa debe cambiar a 0
        stage_manual.invalidate_recordset(['progress_pct'])
        self.assertEqual(stage_manual.progress_pct, 0.0)

    def test_05_strict_stage_locking(self):
        """Verifica que NO se puede cambiar etapa en presupuesto validado."""
        from odoo.exceptions import UserError
        # El presupuesto 'self.budget' ya está validado desde setUpClass
        
        # Intentar cambiar etapa de line1
        # Debe fallar con UserError
        new_stage = self.env['building.work.stage'].create({
            'name': 'Otra Etapa',
            'work_id': self.work.id,
        })
        
        with self.assertRaises(UserError):
            self.line1.write({'stage_id': new_stage.id})
            
        # Reabrir, cambiar, y volver a validar = OK
        # action_set_draft requiere grupo Director
        
        # Opción 1: Crear usuario director (mejor práctica)
        director = self.env['res.users'].create({
            'name': 'Director Test',
            'login': 'director_test',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('building_dashboard.group_building_director').id
            ])]
        })
        
        self.budget.with_user(director).action_set_draft()
        self.line1.write({'stage_id': new_stage.id})
        self.assertEqual(self.line1.stage_id, new_stage)
        self.budget.action_validate()
