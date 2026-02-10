
# -*- coding: utf-8 -*-
"""
Script de Verificación QA - Etapa 4.1: Costos Operativos
Ejecutar con: python3 verify_stage_4_1.py
"""
import xmlrpc.client
import sys
import time

# Configuración
URL = 'http://localhost:8019'
DB = 'odoo19ce'
USER = 'admin'
PASS = 'admin'

def title(msg):
    print(f"\n{'='*60}")
    print(f" {msg}")
    print(f"{'='*60}")

def step(msg):
    print(f" >> {msg}")

def check(condition, msg):
    if condition:
        print(f" [PASS] {msg}")
    else:
        print(f" [FAIL] {msg}")
        # sys.exit(1) # No salir, para ver todos los fallos

try:
    title("INICIANDO QA - ETAPA 4.1: COSTOS OPERATIVOS")
    
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, USER, PASS, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

    if not uid:
        print("Error de autenticación")
        sys.exit(1)

    # 1. SETUP
    step("Creando Obra de Prueba...")
    work_id = models.execute_kw(DB, uid, PASS, 'building.work', 'create', [{
        'name': 'Obra QA Costos 4.1',
        'state': 'running',
        'overall_progress': 10.0 # Simular avance previo
    }])
    
    # Crear Presupuesto y Partida
    budget_id = models.execute_kw(DB, uid, PASS, 'building.budget', 'create', [{
        'work_id': work_id,
        'name': 'Presupuesto QA',
        'state': 'validated'
    }])
    
    chapter_id = models.execute_kw(DB, uid, PASS, 'building.budget.chapter', 'create', [{
        'budget_id': budget_id,
        'name': 'Capítulo QA'
    }])

    budget_line_id = models.execute_kw(DB, uid, PASS, 'building.budget.line', 'create', [{
        'chapter_id': chapter_id,
        'code': 'P001',
        'name': 'Partida QA',
        'qty': 10,
        'price_unit': 100, # Total 1000
    }])

    step("Obra creada ID: {}".format(work_id))

    # 2. COSTO ADICIONAL
    title("PRUEBA 1: Costo Adicional (Indirecto)")
    
    # Intentar asignar budget_line a costo adicional (debe fallar o limpiarse)
    # Nota: la constraint es backend. El onchange es UI. Probamos constraint.
    # Odoo API create no dispara onchange por defecto, así que probamos la constraint pura.

    try:
        models.execute_kw(DB, uid, PASS, 'building.work.cost', 'create', [{
            'work_id': work_id,
            'name': 'Gasto Indebido',
            'cost_type': 'additional',
            'budget_line_id': budget_line_id,
            'qty': 1,
            'unit_cost': 100
        }])
        check(False, "Constraint falló: Se permitió costo 'additional' con partida.")
    except Exception as e:
        check(True, "Constraint OK: Bloqueó costo 'additional' con partida.")

    # Crear correcto
    cost_add_id = models.execute_kw(DB, uid, PASS, 'building.work.cost', 'create', [{
        'work_id': work_id,
        'name': 'Clavos y Herramientas',
        'cost_type': 'additional',
        'qty': 5,
        'unit_cost': 50 # Total 250
    }])
    step(f"Costo Adicional creado ID: {cost_add_id} (Monto: 250.0)")

    # Verificar Totales en Obra
    work = models.execute_kw(DB, uid, PASS, 'building.work', 'read', [work_id], 
                           ['executed_additional_amount', 'executed_total_amount', 'overall_progress'])
    
    check(work[0]['executed_additional_amount'] == 250.0, "Total Adicional actualizado: 250.0")
    check(work[0]['executed_total_amount'] == 250.0, "Total Ejecutado actualizado: 250.0")
    check(work[0]['overall_progress'] == 10.0, "Avance Físico INTACTO (10.0%)")

    # 3. COSTO PRESUPUESTADO
    title("PRUEBA 2: Costo Presupuestado (Directo)")

    # Intentar sin partida (debe fallar)
    try:
        models.execute_kw(DB, uid, PASS, 'building.work.cost', 'create', [{
            'work_id': work_id,
            'name': 'Falta Partida',
            'cost_type': 'budgeted',
            'qty': 1,
            'unit_cost': 100
        }])
        check(False, "Constraint falló: Se permitió costo 'budgeted' sin partida.")
    except Exception as e:
        check(True, "Constraint OK: Bloqueó costo 'budgeted' sin partida.")

    # Crear correcto
    cost_bud_id = models.execute_kw(DB, uid, PASS, 'building.work.cost', 'create', [{
        'work_id': work_id,
        'name': 'Cemento para Partida P001',
        'cost_type': 'budgeted',
        'budget_line_id': budget_line_id,
        'qty': 2,
        'unit_cost': 200 # Total 400
    }])
    step(f"Costo Presupuestado creado ID: {cost_bud_id} (Monto: 400.0)")

    # Verificar Totales en Obra (debe sumar acumulado)
    work = models.execute_kw(DB, uid, PASS, 'building.work', 'read', [work_id], 
                           ['executed_budgeted_amount', 'executed_additional_amount', 'executed_total_amount', 'overall_progress'])
    
    check(work[0]['executed_budgeted_amount'] == 400.0, "Total Presupuestado actualizado: 400.0")
    check(work[0]['executed_additional_amount'] == 250.0, "Total Adicional se mantiene: 250.0")
    check(work[0]['executed_total_amount'] == 650.0, "Total Ejecutado Global: 650.0")
    check(work[0]['overall_progress'] == 10.0, "Avance Físico sigue INTACTO")

    # 4. MODIFICACiÓN
    title("PRUEBA 3: Modificación y Recálculo")
    
    models.execute_kw(DB, uid, PASS, 'building.work.cost', 'write', [[cost_add_id], {
        'qty': 10 # 10 * 50 = 500 (antes 250) -> +250
    }])
    step("Modificada cantidad costo adicional (250 -> 500)")

    work = models.execute_kw(DB, uid, PASS, 'building.work', 'read', [work_id], ['executed_total_amount'])
    check(work[0]['executed_total_amount'] == 900.0, "Total recalculado correctamente (400 + 500 = 900)")

    # 5. ELIMINACIÓN
    title("PRUEBA 4: Eliminación")
    
    models.execute_kw(DB, uid, PASS, 'building.work.cost', 'unlink', [[cost_bud_id]])
    step("Eliminado costo presupuestado (400)")

    work = models.execute_kw(DB, uid, PASS, 'building.work', 'read', [work_id], ['executed_total_amount', 'executed_budgeted_amount'])
    check(work[0]['executed_budgeted_amount'] == 0.0, "Total Presupuestado vuelve a 0")
    check(work[0]['executed_total_amount'] == 500.0, "Total Global ajustado a 500")

    title("QA FINALIZADO EXITOSAMENTE")

except Exception as e:
    print(f"\n[ERROR CRÍTICO] {e}")
    sys.exit(1)
