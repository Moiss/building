import logging
from odoo import api, SUPERUSER_ID

def run(env):
    """
    Script de verificación para Etapa 3.4: Gastos Reales
    """
    print("\n[VERIFICACIÓN] Iniciando prueba de Etapa 3.4...")
    
    # 1. Crear Obra
    work = env['building.work'].create({
        'name': 'Obra de Prueba Stage 3.4',
        'real_source': 'internal',
    })
    print(f"[OK] Obra creada: {work.name}")
    
    # 2. Crear Presupuesto (en Borrador)
    budget = env['building.budget'].create({
        'name': 'Presupuesto Base',
        'work_id': work.id,
        'state': 'draft', # Crear en borrador para poder agregar lineas
        'total_amount': 10000.0,
    })
    # Forzar el computado si es necesario, o crear lineas
    # Como total_amount es computado, creamos una linea
    chapter = env['building.budget.chapter'].create({
        'budget_id': budget.id,
        'name': 'Capítulo 1',
    })
    line = env['building.budget.line'].create({
        'chapter_id': chapter.id,
        'code': '1',
        'name': 'Concepto de Prueba',
        'amount': 10000.0, 
    })
    
    # Validar el presupuesto ahora si
    budget.action_validate()
    # Recalcular
    budget._compute_totals()
    work._compute_budget_kpis()
    
    print(f"[OK] Presupuesto creado con Total: {work.budget_total}")
    
    # 3. Verificar Amount Paid inicial
    if work.amount_paid != 0.0:
        print(f"[ERROR] Amount Paid inicial debería ser 0.0, es {work.amount_paid}")
    else:
        print(f"[OK] Amount Paid inicial es 0.0")
        
    # 4. Crear Gasto Real
    real_line = env['building.real.line'].create({
        'work_id': work.id,
        'budget_line_id': line.id,
        'name': 'Compra de Cemento',
        'amount': 2500.0,
        'date': '2026-01-26',
    })
    print(f"[OK] Gasto Real creado por 2500.0")
    
    # 5. Verificar KPI actualizado
    # Forzar recompute si es necesario (en Odoo unit tests es auto, aqui tambien deberia)
    work.invalidate_recordset(['amount_paid'])
    
    print(f"[CHECK] KPI Amount Paid: {work.amount_paid}")
    print(f"[CHECK] KPI Financial Progress: {work.financial_progress}%")
    
    if work.amount_paid == 2500.0:
        print("[SUCCESS] La integración funciona correctamente.")
    else:
        print(f"[FAILURE] El monto pagado no coincide. Esperado: 2500.0, Actual: {work.amount_paid}")

    # Rollback para no ensuciar BD
    env.cr.rollback()
    print("[CLEANUP] Rollback realizado.")

if __name__ == '__main__':
    # Si se corre desde odoo-bin shell, env está disponible
    if 'env' in locals() or 'env' in globals():
        run(env)
