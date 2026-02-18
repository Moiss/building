
print("Searching for ALL form views of building.work...")
views = env['ir.ui.view'].search([('model', '=', 'building.work'), ('type', '=', 'form')])
if not views:
    print("NO FORM VIEWS FOUND for building.work")
else:
    for v in views:
        print(f"VIEW ID: {v.id}")
        print(f"NAME: {v.name}")
        print(f"XML_ID: {v.get_external_id()}")
        print(f"PRIORITY: {v.priority}")
        if 'real_source' in v.arch_db:
             print(">>> CONTAINS 'real_source'")
        else:
             print(">>> CLEAN")
        print("-" * 20)
