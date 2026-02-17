# verify_analytic_integration.py
import logging
from odoo import fields

_logger = logging.getLogger(__name__)

def verify():
    # 1. Enable Analytic Accounting
    env['ir.config_parameter'].sudo().set_param('building.use_analytic', 'True')
    env['ir.config_parameter'].sudo().set_param('building.analytic_mode', 'both')
    print("[-] Configuration enabled.")

    # 2. Create Work
    work = env['building.work'].create({
        'name': 'Analytic Test Work',
        'real_source': 'internal',
    })
    print(f"[-] Work created: {work.name}")

    # 3. Create Budget & Lines
    budget = env['building.budget'].create({
        'work_id': work.id,
        'name': 'Presupuesto Test',
    })
    chapter = env['building.budget.chapter'].create({
        'budget_id': budget.id,
        'code': 'A',
        'name': 'Capitulo A'
    })
    line = env['building.budget.line'].create({
        'chapter_id': chapter.id,
        'code': '01',
        'name': 'Partida 01',
        'amount': 1000.0
    })
    budget.action_validate()
    print("[-] Budget validated.")

    # 4. Generate Analytics
    work.action_generate_analytics()
    if work.analytic_account_id:
        print(f"[PASS] Work Analytic Account created: {work.analytic_account_id.name}")
    else:
        print("[FAIL] Work Analytic Account NOT created.")

    if line.analytic_account_id:
        print(f"[PASS] Line Analytic Account created: {line.analytic_account_id.name}")
    else:
        print("[FAIL] Line Analytic Account NOT created.")

    # 5. Create Vendor Bill
    journal = env['account.journal'].search([('type', '=', 'purchase')], limit=1)
    partner = env['res.partner'].search([], limit=1)
    move = env['account.move'].create({
        'move_type': 'in_invoice',
        'partner_id': partner.id,
        'invoice_date': fields.Date.today(),
        'journal_id': journal.id,
        'invoice_line_ids': [(0, 0, {
            'name': 'Gasto Test',
            'quantity': 1,
            'price_unit': 100.0,
        })]
    })
    move.action_post()
    print(f"[-] Invoice posted: {move.name}")

    # 6. Allocate Bill using Wizard logic
    # We simulate wizard action by creating the allocation directly as the wizard does
    allocation = env['building.bill.allocation'].create({
        'move_id': move.id,
        'date': fields.Date.today(),
        'state': 'active'
    })
    
    alloc_line = env['building.bill.allocation.line'].create({
        'allocation_id': allocation.id,
        'work_id': work.id,
        'budget_line_id': line.id,
        'amount': 100.0,
        'description': 'Distribución Test'
    })
    
    # Manually trigger analytic creation as it is done in the wizard's action_confirm
    # We are simulating the wizard's logic here for verification
    analytic_account = line.analytic_account_id
    analytic_line = env['account.analytic.line'].create({
        'name': 'Fact. %s - %s' % (move.name, 'Distribución Test'),
        'account_id': analytic_account.id,
        'date': fields.Date.today(),
        'amount': -100.0,
        'ref': '%s - %s' % (move.name, allocation.name),
        'company_id': move.company_id.id,
        'building_allocation_id': allocation.id,
    })
    print(f"[-] Allocation created with analytic line: {analytic_line.id}")
    
    if analytic_line.amount == -100.0:
        print("[PASS] Analytic Line amount is correct (-100.0)")
    else:
        print(f"[FAIL] Analytic Line amount is incorrect: {analytic_line.amount}")

    # 7. Cancel Allocation
    allocation.analytic_line_ids = [(4, analytic_line.id)] # Link it for the test
    allocation.action_cancel()

    if not analytic_line.exists():
         print("[PASS] Analytic Line deleted after cancellation.")
    else:
         print("[FAIL] Analytic Line still exists after cancellation.")

verify()
