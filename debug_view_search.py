# -*- coding: utf-8 -*-
import odoo
from odoo import api, SUPERUSER_ID

def run(env):
    print("Searching for 'real_source' in ir.ui.view...")
    views = env['ir.ui.view'].search_read([('arch_db', 'like', 'real_source')], ['name', 'xml_id', 'model', 'type'])
    if not views:
        print("No views found referencing 'real_source'.")
    else:
        for v in views:
            print(f"FOUND VIEW: ID={v['id']}, Name={v['name']}, XML_ID={v.get('xml_id')}, Model={v['model']}")
            
    print("\nSearching for 'real_source' in ir.model.fields...")
    fields = env['ir.model.fields'].search_read([('name', '=', 'real_source')], ['model', 'name', 'state'])
    if not fields:
        print("No fields found named 'real_source'.")
    else:
        for f in fields:
            print(f"FOUND FIELD: Model={f['model']}, Name={f['name']}, State={f['state']}")

if __name__ == "__main__":
    # Boilerplate to run as script
    import sys
    import os
    
    # Add odoo path
    sys.path.append(os.path.abspath("../odoo-19.0"))
    
    # Configure Odoo
    import odoo.tools.config
    odoo.tools.config.parse_config(['-c', '../proyectos/odoo.conf', '-d', 'odoo19ce'])
    
    # Connect
    registry = odoo.registry(odoo.tools.config['db_name'])
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        run(env)
