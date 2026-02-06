# -*- coding: utf-8 -*-
from odoo.tests import common

from odoo.tests import common, tagged

@tagged('post_install', '-at_install', 'building_dashboard')
class TestTrafficLight(common.TransactionCase):
    
    def setUp(self):
        super(TestTrafficLight, self).setUp()
        self.Stage = self.env['building.work.stage']
        self.BudgetLine = self.env['building.budget.line']
        self.RealLine = self.env['building.real.line']
        self.Work = self.env['building.work']
        
        # Create minimal setup
        self.work = self.Work.create({'name': 'Work Test Traffic Light'})
        self.stage = self.Stage.create({'name': 'Stage TL', 'work_id': self.work.id})
        
        # Budget Chapter wrapper (needed for line creation usually)
        self.chapter = self.env['building.budget.chapter'].create({
            'name': 'Chapter 1',
            'budget_id': self.env['building.budget'].create({
                'work_id': self.work.id, 'name': 'Budget 1'
            }).id
        })

    def test_01_green_case(self):
        """ Test Green case: Executed <= 90% of Budget """
        # Budget: 1000
        b_line = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '01', 'name': 'Line 1', 'amount': 1000.0,
            'stage_id': self.stage.id
        })
        
        # Executed: 500 (50%) -> Green
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 500.0,
            'name': 'Real 1'
        })
        
        self.stage.invalidate_recordset() # Force reload if needed, though store=True should handle it
        self.assertEqual(self.stage.traffic_light, 'green', "50% should be Green")
        self.assertEqual(self.stage.consume_pct, 50.0)

        # Executed: 900 (90%) -> Green (<= 90)
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 400.0, # Total 900
            'name': 'Real 2'
        })
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'green', "90% Exact should be Green")
        self.assertEqual(self.stage.consume_pct, 90.0)

    def test_02_yellow_case(self):
        """ Test Yellow case: 90% < Executed <= 100% """
        b_line = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '02', 'name': 'Line 2', 'amount': 1000.0,
            'stage_id': self.stage.id
        })
        
        # Executed: 910 (91%) -> Yellow
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 910.0,
            'name': 'Real 1'
        })
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'yellow', "91% should be Yellow")

        # Executed: 1000 (100%) -> Yellow (<= 100)
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 90.0, # Total 1000
            'name': 'Real 2'
        })
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'yellow', "100% Exact should be Yellow")

    def test_03_red_case(self):
        """ Test Red case: Executed > 100% """
        b_line = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '03', 'name': 'Line 3', 'amount': 1000.0,
            'stage_id': self.stage.id
        })
        
        # Executed: 1010 (101%) -> Red
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 1010.0,
            'name': 'Real 1'
        })
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'red', "101% should be Red")

    def test_04_edge_zero_budget(self):
        """ Test Edge Case: Budget 0 """
        b_line = self.BudgetLine.create({
            'chapter_id': self.chapter.id,
            'code': '04', 'name': 'Line 4', 'amount': 0.0, # Zero Budget
            'stage_id': self.stage.id
        })
        
        # Executed: 0 -> Green
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'green', "Budget 0, Real 0 should be Green")
        
        # Executed: 10 -> Red
        self.RealLine.create({
            'work_id': self.work.id,
            'stage_id': self.stage.id,
            'budget_line_id': b_line.id,
            'amount': 10.0,
            'name': 'Real 1'
        })
        self.stage.invalidate_recordset()
        self.assertEqual(self.stage.traffic_light, 'red', "Budget 0, Real > 0 should be Red")
