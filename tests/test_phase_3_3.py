from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import fields

@tagged('post_install', '-at_install')
class TestPhase33(TransactionCase):

    def setUp(self):
        super(TestPhase33, self).setUp()
        
        # Crear datos base
        self.work = self.env['building.work'].create({'name': 'Test Work 3.3'})
        self.stage = self.env['building.work.stage'].create({
            'name': 'Stage 1',
            'work_id': self.work.id,
            'state': 'planning'
        })
        
        self.budget = self.env['building.budget'].create({
            'name': 'Budget Test',
            'work_id': self.work.id
        })
        self.chapter = self.env['building.budget.chapter'].create({
            'name': 'Chapter 1',
            'budget_id': self.budget.id,
            'code': '01'
        })
        
        # Partida con importe 1000
        self.line = self.env['building.budget.line'].create({
            'name': 'Line 1',
            'chapter_id': self.chapter.id,
            'code': '01.01',
            'amount': 1000.0,
            # No stage initially
        })

    def test_01_wizard_stage_assignment(self):
        """Test: Wizard allows assigning stage if missing."""
        self.assertFalse(self.line.stage_id)
        
        # Abrir wizard
        wizard = self.env['building.budget.progress.wizard'].create({
            'line_id': self.line.id,
            'stage_id': self.stage.id, # Asignar etapa
            'date': fields.Date.today(),
            'percent_period': 10.0,
            'notes': 'Advance 1'
        })
        
        # Confirmar
        wizard.action_confirm()
        
        # Verificar asignación
        self.assertEqual(self.line.stage_id, self.stage, "Stage should be assigned to line")
        self.assertEqual(self.line.physical_progress, 10.0, "Progress should be 10%")

    def test_02_scale_constraints(self):
        """Test: Scale constraints (0-100) and Max Registrable."""
        self.line.stage_id = self.stage
        
        # Registrar 50%
        self.env['building.budget.progress'].create({
            'line_id': self.line.id,
            'percent_period': 50.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
            'date': fields.Date.today()
        })
        self.assertEqual(self.line.physical_progress, 50.0)
        
        # Intentar registrar 60% (Total 110%) -> Debe fallar
        wizard = self.env['building.budget.progress.wizard'].new({
            'line_id': self.line.id,
            'percent_period': 60.0
        })
        # Forzar compute
        wizard._compute_max_registrable()
        self.assertEqual(wizard.max_registrable, 50.0)
        
        with self.assertRaises(ValidationError):
            wizard._check_percent_limit()

    def test_03_executed_amount_calculation(self):
        """Test: Executed Amount calculation."""
        self.line.stage_id = self.stage
        
        # Avance 25% de 1000 = 250
        self.env['building.budget.progress'].create({
            'line_id': self.line.id,
            'percent_period': 25.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
            'date': fields.Date.today()
        })
        
        self.assertEqual(self.line.physical_progress, 25.0)
        self.assertEqual(self.line.executed_amount, 250.0)

    def test_04_delete_protection(self):
        """Test: Cannot delete stage with progress."""
        self.line.stage_id = self.stage
        
        # Registrar avance
        self.env['building.budget.progress'].create({
            'line_id': self.line.id,
            'percent_period': 10.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
            'date': fields.Date.today()
        })
        
        # Intentar borrar etapa
        with self.assertRaises(UserError):
            self.stage.unlink()
            
    def test_05_weighted_average(self):
        """Test: Stage Weighted Average."""
        # Line 1: 1000 amount, 50% progress
        self.line.stage_id = self.stage
        self.env['building.budget.progress'].create({
            'line_id': self.line.id,
            'percent_period': 50.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
            'date': fields.Date.today()
        })
        
        # Line 2: 3000 amount, 25% progress
        line2 = self.env['building.budget.line'].create({
            'name': 'Line 2',
            'chapter_id': self.chapter.id,
            'code': '01.02',
            'amount': 3000.0,
            'stage_id': self.stage.id
        })
        # Registrar avance directamente (wizard logic ya probada en test 01)
        self.env['building.budget.progress'].create({
            'line_id': line2.id,
            'percent_period': 25.0,
            'state': 'confirmed',
            'user_id': self.env.user.id,
            'date': fields.Date.today()
        })
        
        # Calculation:
        # Total Amount = 1000 + 3000 = 4000
        # Weighted Progress = (1000 * 0.50) + (3000 * 0.25) = 500 + 750 = 1250
        # Stage Progress = 1250 / 4000 = 0.3125 (31.25%)
        
        self.stage.invalidate_recordset(['progress_pct']) # Force recompute
        self.assertAlmostEqual(self.stage.progress_pct, 31.25, places=2)
