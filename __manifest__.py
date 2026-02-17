# -*- coding: utf-8 -*-
# Módulo: building_dashboard
# Dashboard de Obra para OdooBuilding con integración IA (Gemini + OpenAI)
{
    'name': 'Control de Obras',
    'version': '19.0.1.0.0',
    'summary': 'Dashboard de Obra: Presupuesto vs Real, Etapas y Control Operativo — con IA Integrada',
    'description': """
OdooBuilding - Dashboard Principal de Obra
===========================================

Módulo que implementa la Pantalla 1 (Dashboard de Obra) para el proyecto OdooBuilding.

Funcionalidades principales:
- KPIs de Obra: Presupuesto Total, Comprometido, Pagado y Disponible
- Alertas de desviación y aprobaciones pendientes
- Etapas/Frentes en Kanban con registro rápido de avances
- Compras y gastos con flujo: Solicitar → Autorizar → Comprar → Pagar
- Asistente IA (Gemini + OpenAI) para parametrizar y acelerar decisiones

Roles soportados:
- Director de Obra
- Administrador de Obra
- Compras
- Contabilidad
    """,
    'author': 'OdooBuilding',
    'website': 'https://odoobuilding.com',
    'category': 'Construction/Project',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
        'account',
        'analytic',
    ],
    'data': [
        # Seguridad (primero)
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        # Vistas
        'views/account_move_inherit_views.xml',
        'views/bill_allocation_views.xml',
        'views/allocate_bill_wizard_views.xml',
        'views/building_ai_config_wizard_views.xml',
        'views/building_change_real_source_wizard_views.xml',
        'views/building_chapter_loader_wizard_views.xml',
        'views/consolidate_budget_wizard_views.xml',
        'views/building_work_views.xml',
        'views/building_stage_views.xml',
        'views/building_alert_views.xml',
        'views/building_budget_views.xml',
        'views/building_progress_views.xml',  # FASE 3.2: Avance Físico
        'views/building_budget_progress_views.xml',  # FASE 3.3: Avance por Partida
        'views/building_real_line_views.xml',        # FASE 3.4: Gastos Reales
        'views/work_cost_views.xml',                 # FASE 4.1: Costos Operativos
        'views/work_evidence_views.xml',             # FASE 4.2: Evidencias
        'views/menus.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
