
views = env['ir.ui.view'].search([('model', '=', 'building.work'), ('type', '=', 'form')])
if not views:
    print("NO FORM VIEWS FOR building.work")
else:
    for v in views:
        xml_id = "Unknown"
        try:
             xml_id = v.get_external_id()
        except:
             pass
        print(f"VIEW: ID={v.id}, Name={v.name}, XML_ID={xml_id}")
        print(f"ARCH START: {v.arch_db[:100]}...")
