# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestConsolidatedFeatures(TransactionCase):

    def setUp(self):
        super(TestConsolidatedFeatures, self).setUp()
        self.Work = self.env['building.work']
        self.Budget = self.env['building.budget']
        self.Chapter = self.env['building.budget.chapter']
        self.Line = self.env['building.budget.line']
        self.Stage = self.env['building.work.stage']

        self.work = self.Work.create({'name': 'Test Work'})
        self.budget = self.Budget.create({
            'name': 'Test Budget',
            'work_id': self.work.id,
            'duration_months': 12
        })
        self.chapter = self.Chapter.create({
            'budget_id': self.budget.id,
            'code': 'CAP-01',
            'name': 'Test Chapter'
        })

    def test_normalization(self):
        """Verify Title Case and Uppercase normalization."""
        # Test Stage Name
        stage = self.Stage.create({
            'name': '  stage name  ',
            'work_id': self.work.id
        })
        self.assertEqual(stage.name, 'Stage Name', "Stage name should be Title Case and trimmed")

        # Test Chapter
        chapter = self.Chapter.create({
            'budget_id': self.budget.id,
            'code': '  cap-99  ',
            'name': '  chapter name  '
        })
        self.assertEqual(chapter.code, 'CAP-99', "Chapter code should be Uppercase and trimmed")
        self.assertEqual(chapter.name, 'Chapter Name', "Chapter name should be Title Case")

        # Test Budget Line
        line = self.Line.create({
            'chapter_id': self.chapter.id,
            'code': '  l-01  ',
            'name': '  line name  ',
            'amount': 1000
        })
        self.assertEqual(line.code, 'L-01', "Line code should be Uppercase")
        self.assertEqual(line.name, 'Line Name', "Line name should be Title Case")

    def test_drill_down_actions_work(self):
        """Verify Work Dashboard drill-down actions."""
        # Create data to match filters
        line1 = self.Line.create({
            'chapter_id': self.chapter.id,
            'code': 'L1',
            'name': 'Distributed',
            'amount': 1000,
            'period_from': 1,
            'period_to': 1
        })
        line1.action_distribute_uniform() # distribute > 0
        
        line2 = self.Line.create({
            'chapter_id': self.chapter.id,
            'code': 'L2',
            'name': 'Undistributed',
            'amount': 2000
        })
        # line2 has 0 distributed -> amount_undistributed = 2000

        # Refresh computations
        self.budget.action_validate()
        
        # Action Committed
        action_committed = self.work.action_view_committed()
        domain = action_committed['domain']
        # Domain should filter distributed > 0
        # Manual check of domain logic?
        self.assertIn(('total_distributed', '>', 0), domain)
        self.assertEqual(action_committed['res_model'], 'building.budget.line')

        # Action Available
        action_available = self.work.action_view_available()
        domain = action_available['domain']
        self.assertIn(('amount_undistributed', '>', 0), domain)

    def test_drill_down_actions_budget(self):
        """Verify Budget drill-down actions."""
        line = self.Line.create({
            'chapter_id': self.chapter.id,
            'code': 'L3',
            'name': 'Difference',
            'amount': 1000
        })
        # Distribute only 500 manualy (creating difference)
        self.env['building.budget.period.value'].create({
            'line_id': line.id,
            'period_number': 1,
            'amount': 500
        })
        line._compute_distribution() # Force compute
        
        self.assertTrue(line.has_warning)
        
        action = self.budget.action_view_difference_lines()
        domain = action['domain']
        self.assertIn(('has_warning', '=', True), domain)

    def test_drill_down_actions_stage(self):
        """Verify Stage drill-down actions."""
        stage = self.Stage.create({
            'name': 'Test Stage',
            'work_id': self.work.id
        })
        
        # Test Risky Lines
        action = stage.action_view_risky_lines()
        domain = action['domain']
        self.assertIn(('traffic_light', 'in', ['yellow', 'red']), domain)
        
        # Test Variance Lines
        action = stage.action_view_variance_lines()
        domain = action['domain']
        self.assertIn(('variance_amount', '<', 0), domain)
