# -*- coding: utf-8 -*-
"""
Script de limpieza de duplicados en asignación de partidas a etapas.
Ejecutar con: python3 odoo-bin shell -c odoo.conf -d <db_name> < cleanup_duplicates.py
"""
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)

def clean_duplicates(env):
    print("=== INICIANDO LIMPIEZA DE DUPLICADOS ===")
    
    # 1. Buscar todas las etapas con partidas
    stages = env['building.work.stage'].search([])
    total_deleted = 0
    
    for stage in stages:
        print(f"Procesando Etapa: {stage.name} (ID: {stage.id})")
        
        # Agrupar por Base Budget Line ID
        # Solo nos importan las que vienen de un presupuesto base
        lines = env['building.budget.line'].search([
            ('stage_id', '=', stage.id),
            ('base_budget_line_id', '!=', False)
        ])
        
        by_base = defaultdict(list)
        for line in lines:
            by_base[line.base_budget_line_id.id].append(line)
            
        stage_deleted = 0
        
        for base_id, group in by_base.items():
            if len(group) > 1:
                # ESTRATEGIA WINNER:
                # 1. El que tenga mayor avance físico
                # 2. El que tenga mayor gasto real asignado (si hubiera)
                # 3. El más reciente (ID más alto)
                
                # Ordenar descendente: (progress, id)
                group.sort(key=lambda l: (l.physical_progress, l.id), reverse=True)
                
                winner = group[0]
                losers = group[1:]
                
                print(f"  - Duplicado en BaseLine ID {base_id}: {len(group)} registros.")
                print(f"    -> Winner: {winner.id} (Progress: {winner.physical_progress}%)")
                
                for loser in losers:
                    print(f"    -> Eliminando Loser: {loser.id} (Progress: {loser.physical_progress}%)")
                    
                    # REASIGNAR DEPENDENCIAS ANTES DE BORRAR?
                    # Si el loser tiene real_line_ids, pasarlos al winner?
                    if loser.real_line_ids:
                        print(f"       Reasignando {len(loser.real_line_ids)} gastos reales al winner.")
                        loser.real_line_ids.write({'budget_line_id': winner.id})
                        
                    # Si tiene progress_ids (historial), pasarlos al winner?
                    if loser.progress_ids:
                         print(f"       Reasignando {len(loser.progress_ids)} registros de avance al winner.")
                         loser.progress_ids.write({'line_id': winner.id})
                    
                    try:
                        loser.unlink()
                        stage_deleted += 1
                        total_deleted += 1
                    except Exception as e:
                        print(f"    Error al eliminar {loser.id}: {e}")
        
        if stage_deleted > 0:
            print(f"  Etapa Finalizada. Eliminados: {stage_deleted}")
            
            # Recomputar KPIs etapa
            stage._compute_risky_lines()
            # stage._compute_financial_data() # Expensive?
            
    # Forzar recálculo global de obras afectadas
    works = stages.mapped('work_id')
    for work in works:
        print(f"Recomputando KPIs de Obra: {work.name}")
        work._compute_budget_kpis()
        
    print(f"=== FIN DE LIMPIEZA. Total Eliminados: {total_deleted} ===")
    env.cr.commit()

if __name__ == '__main__':
    # Esto permite correrlo dentro de 'odoo shell' si se hace import o exec
    if 'env' in locals():
        clean_duplicates(env)
