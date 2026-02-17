from odoo import fields

# Start shell: python odoo-bin shell -d building_dashboard ...
work = env['building.work'].search([('name', 'ilike', 'CASA DEMO')], limit=1)
if work:
    print(f"Work: {work.name} (ID: {work.id})")
    print(f"has_active_consolidated: {work.has_active_consolidated}")
    print(f"Budget Count: {len(work.budget_ids)}")
    for b in work.budget_ids:
        print(f" - Budget: {b.name} | Type: {b.budget_type} | Active: {b.active} | State: {b.state}")
        
    # Force recompute to check if it changes
    work._compute_has_active_consolidated()
    print(f"Recomputed has_active_consolidated: {work.has_active_consolidated}")
else:
    print("Work 'CASA DEMO' not found.")
