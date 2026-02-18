
filters = env['ir.filters'].search([('domain', 'ilike', 'real_source')])
if filters:
    for f in filters:
        print(f"FOUND FILTER: ID={f.id}, Name={f.name}, Model={f.model_id}, Domain={f.domain}")
else:
    print("NO FILTERS FOUND")

actions = env['ir.actions.act_window'].search(['|', ('domain', 'ilike', 'real_source'), ('context', 'ilike', 'real_source')])
if actions:
    for a in actions:
        print(f"FOUND ACTION: ID={a.id}, Name={a.name}, Domain={a.domain}, Context={a.context}")
else:
    print("NO ACTIONS FOUND")
