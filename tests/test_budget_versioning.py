from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
_logger.info("LOADING TEST BUDGET VERSIONING")

class TestBudgetVersioning(TransactionCase):

    def setUp(self):
        super(TestBudgetVersioning, self).setUp()
        self.ModelBudget = self.env['building.budget']
        self.ModelChapter = self.env['building.budget.chapter']
        self.ModelLine = self.env['building.budget.line']
        self.work = self.env['building.work'].create({'name': 'Work Test'})
        
        # Add Director group to user to allow reopening
        group_director = self.env.ref('building_dashboard.group_building_director')
        self.env.user.write({'group_ids': [(4, group_director.id)]})

    def test_r1_budget_versioning(self):
        """R1: Test version increments on validation"""
        # 1. Create Draft Budget
        budget = self.ModelBudget.create({'work_id': self.work.id, 'name': 'Budget Test'})
        self.assertEqual(budget.version_no, 0)
        self.assertEqual(budget.version_label, "Borrador")
        
        # Add a line to allow validation
        chapter = self.ModelChapter.create({'budget_id': budget.id, 'code': 'A', 'name': 'Cap A'})
        self.ModelLine.create({'chapter_id': chapter.id, 'code': '1', 'name': 'Item 1', 'amount': 100})
        
        # 2. Validate -> V1
        budget.action_validate()
        self.assertEqual(budget.version_no, 1)
        self.assertEqual(budget.version_label, "V1")
        self.assertEqual(budget.state, "validated")
        
        # Verify Message
        last_msg = budget.message_ids[0]
        self.assertIn("Presupuesto cerrado: V1", last_msg.body)
        
        # 3. User Error if validating again (Idempotency check / Block)
        with self.assertRaises(UserError):
            budget.action_validate()
            
        # 4. Reopen
        budget.action_set_draft()
        self.assertEqual(budget.state, "draft")
        # Version should persist or stay same? Requirement says "Si se reabre y se vuelve a cerrar: V2"
        # So version_no is still 1 here.
        self.assertEqual(budget.version_no, 1)
        
        # 5. Validate Again -> V2
        budget.action_validate()
        self.assertEqual(budget.version_no, 2)
        self.assertEqual(budget.version_label, "V2")
        
        last_msg = budget.message_ids[0]
        self.assertIn("Presupuesto cerrado: V2", last_msg.body)

    def test_r2_r3_normalization(self):
        """R2 & R3: Test Uppercase Code and Title Case Name"""
        budget = self.ModelBudget.create({'work_id': self.work.id, 'name': 'Budget Norm'})
        chapter = self.ModelChapter.create({'budget_id': budget.id, 'code': 'A', 'name': 'Cap A'})
        
        # 1. Test Create Normalization
        line = self.ModelLine.create({
            'chapter_id': chapter.id,
            'code': '  p-001 ',
            'name': '  muro   de   contencion  ',
            'amount': 100
        })
        
        self.assertEqual(line.code, "P-001", "Code should be trimmed and uppercase")
        self.assertEqual(line.name, "Muro De Contencion", "Name should be Title Case and normalized spaces")
        
        # 2. Test Write Normalization
        line.write({
            'code': 'x-99',
            'name': 'pintura  vinilica'
        })
        self.assertEqual(line.code, "X-99")
        self.assertEqual(line.name, "Pintura Vinilica")
        
    def test_onchange_methods(self):
        """Test onchange methods behavior manually"""
        # Note: onchange tests usually require Form() context, but we can verify specific helper methods strictly
        # or simulate onchange logic if we extracted methods.
        # Since I added _onchange_code_normalize, let's trust it calls the same logic.
        # We can simulate calling it.
        budget = self.ModelBudget.create({'work_id': self.work.id, 'name': 'Budget Norm'})
        chapter = self.ModelChapter.create({'budget_id': budget.id, 'code': 'A', 'name': 'Cap A'})
        
        # Create line
        line = self.ModelLine.create({'chapter_id': chapter.id, 'code': 'TEMP', 'name': 'Temp', 'amount': 100})
        
        # Simulate UI input
        line.code = ' abc '
        line._onchange_code_normalize()
        self.assertEqual(line.code, "ABC")
        
        line.name = ' hello world '
        line._onchange_name_titlecase()
        self.assertEqual(line.name, "Hello World")
