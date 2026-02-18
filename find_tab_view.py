
print("Searching for views with 'Presupuesto vs Real'...")
views = env['ir.ui.view'].search([('arch_db', 'ilike', 'Presupuesto vs Real')])
if not views:
    print("NO VIEWS FOUND in odoo19ce")
else:
    for v in views:
        print(f"FOUND VIEW: ID={v.id}, Name={v.name}, Model={v.model}, XML_ID={v.get_external_id()}")
        # print(v.arch_db)
