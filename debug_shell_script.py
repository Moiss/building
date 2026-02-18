
views = env['ir.ui.view'].search([('arch_db', 'ilike', 'real_source')])
if not views:
    print("NO VIEWS FOUND WITH real_source")
else:
    for v in views:
        xml_id = "Unknown"
        try:
             xml_id = v.get_external_id()
        except:
             pass
        print(f"FOUND VIEW: ID={v.id}, Name={v.name}, XML_ID={xml_id}, Model={v.model}")

fields = env['ir.model.fields'].search([('name', '=', 'real_source')])
if not fields:
    print("NO FIELDS FOUND WITH real_source")
else:
    for f in fields:
        print(f"FOUND FIELD: Model={f.model}, Name={f.name}, State={f.state}")
