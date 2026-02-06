
# Script de Verificación Manual (Hardening Duplicate Fix)
# Ejecutar via: odoo-bin shell ... < verify_check.py

def run_verification(env):
    print("\n>>> INICIANDO VERIFICACION DE HARDENING <<<\n")

    # 0. ENSURE MODULE INSTALLED
    module = env['ir.module.module'].search([('name', '=', 'building_dashboard')])
    if not module:
        print("[ERROR] Modulo 'building_dashboard' no encontrado en apps.")
        return
    
    if module.state != 'installed':
        print("[INFO] Modulo no instalado (Estado: %s). Intentando instalar..." % module.state)
        try:
            module.button_immediate_install()
            env.cr.commit() # Commit installation
            # Re-fetch environment after registry reload? 
            # Shell might need restart or registry reload.
            # But button_immediate_install reloads registry usually.
            print("[INFO] Instalacion completada. Verificando...")
        except Exception as e:
            print("[ERROR] Fallo la instalacion: %s" % e)
            return

    # Re-check model availability
    if 'building.work' not in env:
        print("[ERROR] Modelo 'building.work' no encontrado tras instalacion.")
        # Try finding why
        return

    # 1. SETUP
    # Crear Obra y Presupuesto
    work = env['building.work'].create({'name': 'Work Verify Hardening'})
    budget = env['building.budget'].create({'work_id': work.id, 'name': 'Budget Verify'})
    
    chapter = env['building.budget.chapter'].create({
        'budget_id': budget.id, 'code': 'TEST', 'name': 'Testing Chapter'
    })
    
    line1 = env['building.budget.line'].create({
        'chapter_id': chapter.id, 'code': '1.01', 'name': 'Line 1', 'amount': 1000.0,
    })
    line2 = env['building.budget.line'].create({
        'chapter_id': chapter.id, 'code': '1.02', 'name': 'Line 2', 'amount': 2000.0,
    })
    
    stage = env['building.work.stage'].create({'name': 'Stage A', 'work_id': work.id})
    print("[OK] Setup completado: Lineas creadas (2 total)")
    
    # 2. TEST WIZARD (WRITE-ONLY)
    wiz = env['building.chapter.loader.wizard'].create({
        'stage_id': stage.id,
        'budget_id': budget.id,
        'chapter_ids': [(6, 0, [chapter.id])],
        'reassign_mode': 'no_reassign'
    })
    wiz.action_load_lines()
    
    # Verify
    if len(chapter.line_ids) != 2:
        print("[FAIL] Se crearon duplicados durante la carga! Total: %s" % len(chapter.line_ids))
    else:
        print("[OK] No se crearon duplicados (Total: 2)")
        
    if line1.stage_id != stage or line2.stage_id != stage:
        print("[FAIL] Las lineas no se asignaron a la etapa correca")
    else:
        print("[OK] Lineas asignadas correctamente a la etapa")

    # 3. TEST CONSOLIDATION (MIGRATION)
    # Crear un duplicado "legacy" manualmente
    dup = env['building.budget.line'].create({
        'chapter_id': chapter.id,
        'code': '1.01',
        'name': 'Line 1 Copy',
        'amount': 1000.0,
        'base_budget_line_id': line1.id, # Link a base
        'stage_id': stage.id,
        'budget_id': budget.id,
    })
    # Reset base stage to simulate it was lost or not set before
    line1.stage_id = False
    
    print("Simulando duplicado legacy... Total lineas: %s" % len(chapter.line_ids))
    
    # Ejecutar consolidacion
    budget.action_consolidate_assigned_lines()
    
    if len(chapter.line_ids) != 2:
        print("[FAIL] Consolidacion fallo al eliminar duplicado. Total: %s" % len(chapter.line_ids))
    else:
        print("[OK] Consolidacion elimino duplicado correctamente")
        
    if line1.stage_id != stage:
        print("[FAIL] La linea base no recupero la etapa del duplicado")
    else:
        print("[OK] La linea base recupero la etapa (Consolidacion exitosa)")
        
    # 4. TEST VALIDATED CONSTRAINTS
    budget.action_validate()
    print("Presupuesto validado.")
    
    # Try mod stage
    try:
        line1.write({'stage_id': False})
        print("[OK] Cambio de Stage permitido en Validado")
    except Exception as e:
        print("[FAIL] Se bloqueo el cambio de Stage en Validado: %s" % e)
        
    # Try mod amount
    try:
        line1.write({'amount': 9999})
        print("[FAIL] NO SE BLOQUEO el cambio de monto en Validado!")
    except Exception as e:
        print("[OK] Cambio de Amount bloqueado correctamente: %s" % e)

    print("\n>>> VERIFICACION COMPLETADA <<<\n")

# Ejecutar
run_verification(env)
env.cr.rollback() # No guardar cambios
