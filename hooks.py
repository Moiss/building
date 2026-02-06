# -*- coding: utf-8 -*-
"""
Hooks de instalación/actualización del módulo.
"""

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Hook ejecutado después de instalar/actualizar el módulo.
    Fuerza el recálculo de campos computados en building.work.
    """
    _logger.info("building_dashboard: Ejecutando post_init_hook - recalculando KPIs...")
    
    # Obtener todas las obras
    works = env['building.work'].search([])
    
    if works:
        # Forzar recálculo de campos computados
        # Esto invalida el caché y fuerza el recálculo
        works._compute_budget_kpis()
        works._compute_amount_available()
        works._compute_financial_progress()
        
        _logger.info(
            "building_dashboard: Recalculados KPIs para %d obras", 
            len(works)
        )
    else:
        _logger.info("building_dashboard: No hay obras para recalcular")
    
    # Asignar usuario admin al grupo Director (Odoo 19 no permite hacerlo via XML)
    try:
        director_group = env.ref('building_dashboard.group_building_director', raise_if_not_found=False)
        admin_user = env.ref('base.user_admin', raise_if_not_found=False)
        if director_group and admin_user:
            director_group.write({'users': [(4, admin_user.id)]})
            _logger.info("building_dashboard: Usuario admin asignado al grupo Director")
    except Exception as e:
        _logger.warning("building_dashboard: No se pudo asignar admin al grupo Director: %s", e)
