# -*- coding: utf-8 -*-
from odoo.tests import common, tagged

@tagged('building_dashboard')
class TestBudgetLineTrafficLight(common.TransactionCase):
    
    def setUp(self):
        super(TestBudgetLineTrafficLight, self).setUp()
        self.BudgetLine = self.env['building.budget.line']
        self.RealLine = self.env['building.real.line']
        self.Work = self.env['building.work']
        self.Stage = self.env['building.work.stage']
        
        # Setup work and stage
        self.work = self.Work.create({'name': 'Work Test Line TL'})
        self.stage = self.Stage.create({'name': 'Stage TL', 'work_id': self.work.id})
        
        # Setup budget
        self.chapter = self.env['building.budget.chapter'].create({
            'name': 'Chapter 1',
            'budget_id': self.env['building.budget'].create({
                'work_id': self.work.id, 'name': 'Budget 1'
            }).id
        })

    def test_01_line_traffic_lights(self):
        """ Test line level traffic lights """
        # 1. Green Line (80%)
        # Budget: 10,000
        line_green = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '01', 'name': 'Line Green', 'amount': 10000.0,
            'stage_id': self.stage.id
        })
        # Real: 8,000
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_green.id,
            'amount': 8000.0,
            'name': 'Real G'
        })
        line_green.invalidate_recordset()
        self.assertEqual(line_green.traffic_light, 'green')
        self.assertEqual(line_green.consume_pct, 80.0)

        # 2. Yellow Line (95%)
        # Budget: 10,000
        line_yellow = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '02', 'name': 'Line Yellow', 'amount': 10000.0,
            'stage_id': self.stage.id
        })
        # Real: 9,500
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_yellow.id,
            'amount': 9500.0,
            'name': 'Real Y'
        })
        line_yellow.invalidate_recordset()
        self.assertEqual(line_yellow.traffic_light, 'yellow')
        self.assertEqual(line_yellow.consume_pct, 95.0)

        # 3. Red Line (110%)
        # Budget: 10,000
        line_red = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '03', 'name': 'Line Red', 'amount': 10000.0,
            'stage_id': self.stage.id
        })
        # Real: 11,000
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_red.id,
            'amount': 11000.0,
            'name': 'Real R'
        })
        line_red.invalidate_recordset()
        self.assertEqual(line_red.traffic_light, 'red')
        self.assertAlmostEqual(line_red.consume_pct, 110.0)
        self.assertEqual(line_red.variance_amount, -1000.0)

    def test_02_edge_cases(self):
        """ Test edge cases: 0 Budget """
        # Budget: 0
        line_zero = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '04', 'name': 'Line Zero', 'amount': 0.0,
            'stage_id': self.stage.id
        })
        
        # Real: 0 -> Green
        line_zero.invalidate_recordset()
        self.assertEqual(line_zero.traffic_light, 'green')
        
        # Real: 1000 -> Red
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_zero.id,
            'amount': 1000.0,
            'name': 'Real Unexpected'
        })
        line_zero.invalidate_recordset()
        self.assertEqual(line_zero.traffic_light, 'red')
        self.assertEqual(line_zero.consume_pct, 999.0)

    def test_03_drill_down(self):
        """ Test stage risky count and drill-down action """
        # Create 1 Red line in the stage
        line_red = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '05', 'name': 'Line Red Drill', 'amount': 100.0,
            'stage_id': self.stage.id
        })
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_red.id,
            'amount': 200.0, # 200%
            'name': 'Real Drill'
        })
        
        # Create 1 Green line in the stage
        line_green = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '06', 'name': 'Line Green Drill', 'amount': 100.0,
            'stage_id': self.stage.id
        })
        self.RealLine.create({
            'work_id': self.work.id,
            'budget_line_id': line_green.id,
            'amount': 50.0, # 50%
            'name': 'Real Green'
        })

        self.stage.invalidate_recordset()
        
        # Verify Count
        self.assertEqual(self.stage.risky_line_count, 1, "Should have 1 risky line")
        
        # Verify Action
        action = self.stage.action_view_risky_lines()
        self.assertEqual(action['res_model'], 'building.budget.line')
        self.assertIn(('stage_id', '=', self.stage.id), action['domain'])
        # Check domain contains the tuple or the list version
        domain_str = str(action['domain'])
        self.assertTrue("'traffic_light', 'in', ['yellow', 'red']" in domain_str or "'traffic_light', 'in', ('yellow', 'red')" in domain_str)
