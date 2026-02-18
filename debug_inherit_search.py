
parent = env.ref('building_dashboard.building_work_view_form', raise_if_not_found=False)
if not parent:
    print("PARENT VIEW NOT FOUND")
else:
    print(f"Parent View ID: {parent.id}")
    children = env['ir.ui.view'].search([('inherit_id', '=', parent.id)])
    if not children:
        print("NO INHERITED VIEWS FOUND")
    else:
        for child in children:
            print(f"CHILD VIEW: ID={child.id}, Name={child.name}, Model={child.model}, XML_ID={child.get_external_id()}")
            print(f"ARCH: {child.arch_db[:100]}...")
