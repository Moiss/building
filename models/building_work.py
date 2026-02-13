# -*- coding: utf-8 -*-
"""
Modelo principal: Obra (building.work)
Entidad raíz del dashboard de construcción con KPIs y relaciones.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BuildingWork(models.Model):
    """
    Modelo de Obra - Entidad principal del dashboard.
    Contiene KPIs financieros, etapas/frentes y alertas.
    """
    _name = 'building.work'
    _description = 'Obra de Construcción'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # === CAMPOS BÁSICOS ===
    name = fields.Char(
        string='Nombre de la Obra',
        required=True,
        tracking=True,
        help='Nombre identificador de la obra'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help='Compañía propietaria de la obra'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('planning', 'Planeación'),
        ('running', 'En Ejecución'),
        ('paused', 'Pausada'),
        ('done', 'Finalizada'),
    ], string='Estado', default='draft', required=True)
    
    # === CAMPOS MONETARIOS (KPIs) ===
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        store=True,
        readonly=True
    )
    
    # === KPIs COMPUTADOS (FASE 3.1 FIX) ===
    # Presupuesto Total: del presupuesto validado (o borrador más reciente)
    budget_total = fields.Monetary(
        string='Presupuesto Total',
        currency_field='currency_id',
        compute='_compute_budget_kpis',
        store=True,
        help='Suma total de partidas del presupuesto vigente'
    )
    
    # Comprometido: total distribuido en periodos (dinero ya asignado)
    amount_committed = fields.Monetary(
        string='Comprometido',
        currency_field='currency_id',
        compute='_compute_budget_kpis',
        store=True,
        help='Total distribuido en periodos (FASE 3.x: control operativo)'
    )
    
    # Pagado: calculado según la fuente real (Fase 3.4)
    amount_paid = fields.Monetary(
        string='Pagado',
        currency_field='currency_id',
        compute='_compute_amount_paid',
        store=True,
        help='Monto pagado real (suma de gastos reales o contabilidad)'
    )
    
    amount_available = fields.Monetary(
        string='Disponible',
        currency_field='currency_id',
        compute='_compute_amount_available',
        store=True,
        help='Presupuesto disponible = Total - Comprometido - Pagado'
    )
    
    # === RELACIONES ===
    stage_ids = fields.One2many(
        'building.work.stage',
        'work_id',
        string='Etapas/Frentes'
    )
    
    alert_ids = fields.One2many(
        'building.work.alert',
        'work_id',
        string='Alertas'
    )
    
    # === GASTOS REALES (FASE 3.4) ===
    real_line_ids = fields.One2many(
        'building.real.line',
        'work_id',
        string='Gastos Reales'
    )

    # === PRESUPUESTO PARAMÉTRICO ===
    budget_ids = fields.One2many(
        'building.budget',
        'work_id',
        string='Presupuestos'
    )

    # === SELECTOR DE PRESUPUESTO (ETAPA 4.3a) ===
    selected_budget_id = fields.Many2one(
        'building.budget',
        string='Presupuesto en Dashboard',
        domain="[('work_id', '=', id)]",
        help="Seleccione qué presupuesto ver en el dashboard. Vacío = muestra la suma de todos.",
        tracking=False,
        ondelete='set null'
    )

    selected_budget_name = fields.Char(
        string='Presupuesto Mostrado',
        compute='_compute_selected_budget_name',
        store=False
    )

    budget_count = fields.Integer(
        string='# Presupuestos',
        compute='_compute_budget_count'
    )
    

    # === CAMPOS COMPUTADOS AUXILIARES ===
    stage_count = fields.Integer(
        string='# Etapas',
        compute='_compute_stage_count'
    )
    
    active_alert_count = fields.Integer(
        string='# Alertas Activas',
        compute='_compute_active_alert_count',
        store=True
    )
    


    # === CAMBIO 1: AVANCE GLOBAL ===
    overall_progress = fields.Float(
        string='Avance Global (%)',
        default=0.0,
        readonly=True, # Gestionado por Engine
        help='Avance global de la obra (promedio ponderado). Calculado por Progress Engine.'
    )

    # === CAMBIO 3: AVANCE FINANCIERO Y COMPARATIVO ===
    financial_progress = fields.Float(
        string='Avance Financiero (%)',
        compute='_compute_financial_progress',
        help='(Pagado + Comprometido) / Presupuesto Total * 100'
    )

    consistency_warning = fields.Boolean(
        string='Alerta Consistencia',
        compute='_compute_consistency_warning',
        help='True si avance financiero > avance físico'
    )

    # === CAMBIO 4: BASE PARA FUTURAS ETAPAS ===
    has_parametric_budget = fields.Boolean(
        string='Tiene Presupuesto Paramétrico',
        default=False,
        help='Indica si la obra utiliza presupuesto paramétrico (fase futura)'
    )

    # === CONFIGURACIÓN DE REGLAS OPERATIVAS (FASE 3.1) ===
    financial_tolerance = fields.Float(
        string='Tolerancia Financiera (%)',
        default=5.0,
        help='Porcentaje de tolerancia para alerta cuando el avance financiero supera al físico'
    )

    days_without_progress = fields.Integer(
        string='Días sin Avance',
        default=7,
        help='Número de días sin registrar avance para generar alerta en etapas activas'
    )

    client_advance_planned = fields.Monetary(
        string='Anticipo Cliente Planeado',
        currency_field='currency_id',
        default=0.0,
        help='Monto de anticipo esperado del cliente para comparar contra anticipos planeados'
    )

    # === GESTIÓN FINANCIERA (FASE 3.4) ===
    real_source = fields.Selection([
        ('internal', 'Interno (Plan A)'),
        ('accounting', 'Contabilidad (Plan B)'),
    ], string='Fuente del Real', default='internal', required=True,
       help='Define de dónde se obtienen los costos reales.')

    real_cutover_date = fields.Date(
        string='Fecha de Corte (Migración)',
        help='Fecha a partir de la cual se usa la Contabilidad y se bloquean registros internos anteriores.'
    )

    # === MÉTODOS COMPUTE ===
    
    def _get_active_budget(self):
        """Obtiene el presupuesto activo de la obra.
        
        Prioridad:
        1. Presupuesto validado más reciente
        2. Presupuesto en borrador más reciente
        3. None si no hay presupuestos
        """
        self.ensure_one()
        # Buscar validado primero
        validated = self.budget_ids.filtered(lambda b: b.state == 'validated')
        if validated:
            return validated[0]
        # Si no hay validado, buscar borrador
        drafts = self.budget_ids.filtered(lambda b: b.state == 'draft')
        if drafts:
            return drafts[0]
        return self.env['building.budget']

    def _get_selected_budget(self):
        """Devuelve el/los presupuestos a mostrar en dashboard.
        
        Si hay selección -> devuelve ese.
        Si no -> devuelve todos los validados/consolidados.
        """
        self.ensure_one()
        if self.selected_budget_id:
            return self.selected_budget_id
        
        # Si no hay selección, retornamos todos los activos (para sumarizar)
        return self.budget_ids.filtered(lambda b: b.state in ['validated', 'consolidated'])

    def action_clear_budget_selection(self):
        """Limpia la selección de presupuesto para mostrar todos."""
        self.ensure_one()
        self.selected_budget_id = False
        # Retornar recarga del form para refrescar KPIs
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.work',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'main',
        }

    @api.depends('selected_budget_id')
    def _compute_selected_budget_name(self):
        for work in self:
            if work.selected_budget_id:
                work.selected_budget_name = work.selected_budget_id.name
            else:
                work.selected_budget_name = _("Todos los presupuestos")

    @api.depends(
        'budget_ids',
        'budget_ids.state',
        'budget_ids.total_amount',
        'budget_ids.total_distributed',
        'selected_budget_id'
    )
    def _compute_budget_kpis(self):
        """Calcula KPIs del presupuesto (Soporte Multi-Presupuesto).
        
        Usa _get_selected_budget() para sumar uno o varios.
        """
        for work in self:
            budgets = work._get_selected_budget()
            if budgets:
                work.budget_total = sum(budgets.mapped('total_amount'))
                work.amount_committed = sum(budgets.mapped('total_distributed'))
            else:
                work.budget_total = 0.0
                work.amount_committed = 0.0

    @api.depends('budget_total', 'amount_committed', 'amount_paid')
    def _compute_amount_available(self):
        """Calcula el monto disponible del presupuesto."""
        for work in self:
            available = work.budget_total - work.amount_committed - work.amount_paid
            work.amount_available = max(0.0, available)

    @api.depends('real_source', 'real_line_ids.amount')
    def _compute_amount_paid(self):
        """Calcula el monto pagado (KPI) según la fuente configurada."""
        for work in self:
            if work.real_source == 'internal':
                work.amount_paid = sum(work.real_line_ids.mapped('amount'))
            else:
                # TODO: Integración contable
                work.amount_paid = 0.0

    @api.depends('stage_ids')
    def _compute_stage_count(self):
        """Cuenta el número de etapas."""
        for work in self:
            work.stage_count = len(work.stage_ids)

    @api.depends('budget_ids')
    def _compute_budget_count(self):
        """Cuenta el número de presupuestos."""
        for work in self:
            work.budget_count = len(work.budget_ids)


    @api.depends('alert_ids', 'alert_ids.is_active')
    def _compute_active_alert_count(self):
        """Cuenta las alertas activas."""
        for work in self:
            work.active_alert_count = len(
                work.alert_ids.filtered(lambda a: a.is_active)
            )

    # === COSTOS OPERATIVOS (ETAPA 4.1) ===
    executed_budgeted_amount = fields.Monetary(
        string='Ejecutado Presupuestado',
        currency_field='currency_id',
        compute='_compute_cost_totals',
        store=True,
        help='Suma de costos operativos ligados a una partida presupuestaria'
    )

    executed_additional_amount = fields.Monetary(
        string='Ejecutado Adicional',
        currency_field='currency_id',
        compute='_compute_cost_totals',
        store=True,
        help='Suma de costos operativos NO ligados a partida (adicionales/indirectos)'
    )

    executed_total_amount = fields.Monetary(
        string='Ejecutado Total',
        currency_field='currency_id',
        compute='_compute_cost_totals',
        store=True,
        help='Suma total de costos operativos (Presupuestados + Adicionales)'
    )

    cost_count = fields.Integer(
        string='# Costos',
        compute='_compute_cost_totals',
        store=True
    )

    cost_budgeted_count = fields.Integer(
        string='# Costos Presupuestados',
        compute='_compute_cost_totals',
        store=True,
        help='Cantidad de costos operativos ligados a partida'
    )

    cost_additional_count = fields.Integer(
        string='# Costos Adicionales',
        compute='_compute_cost_totals',
        store=True,
        help='Cantidad de costos adicionales/indirectos'
    )
    
    cost_ids = fields.One2many(
        'building.work.cost',
        'work_id',
        string='Costos Operativos'
    )

    # === EVIDENCIAS (ETAPA 4.2) ===
    evidence_ids = fields.One2many(
        'building.work.evidence',
        'work_id',
        string='Evidencias'
    )

    evidence_count = fields.Integer(
        string='# Evidencias',
        compute='_compute_evidence_count',
        store=False
    )

    @api.depends('cost_ids', 'cost_ids.amount', 'cost_ids.cost_type')
    def _compute_cost_totals(self):
        """
        Calcula totales de costos operativos usando el Motor Financiero.
        Se enfoca en gastos adicionales (Etapa 4.1 Refactor).
        """
        totals = self.env['building.financial.engine'].get_cost_totals(self.ids)
        for work in self:
            data = totals.get(work.id, {})
            work.executed_budgeted_amount = data.get('executed_budgeted_amount', 0.0)
            work.executed_additional_amount = data.get('executed_additional_amount', 0.0)
            work.executed_total_amount = data.get('executed_total_amount', 0.0)
            # Solo usamos cost_count general para el smart button único
            work.cost_count = data.get('cost_count', 0)
            work.cost_budgeted_count = data.get('cost_budgeted_count', 0)
            work.cost_additional_count = data.get('cost_additional_count', 0)

    def _recompute_cost_totals(self):
        """Método helper para forzar recomputo desde cambios en building.work.cost"""
        # Al ser store=True y tener depends de cost_ids, Odoo maneja la invalidez.
        # Pero si queremos forzar o si usamos SQl directo, este método es útil.
        # Por ahora, confiamos en el depends, pero dejamos el hook por si el motor cambia.
        self._compute_cost_totals()

    def action_view_costs(self):
        """Ver lista de costos operativos (Acción genérica)."""
        self.ensure_one()
        return {
            'name': _('Gastos Adicionales'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.work.cost',
            'view_mode': 'list,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id, 'default_cost_type': 'additional'},
        }

    def action_view_additional_costs(self):
        """Smart button: Ver gastos adicionales de la obra."""
        self.ensure_one()
        return {
            'name': _('Gastos Adicionales'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.work.cost',
            'view_mode': 'list,form',
            'context': {
                'default_work_id': self.id,
                'default_cost_type': 'additional',
            },
        }

    def _compute_evidence_count(self):
        """Cuenta las evidencias de la obra."""
        for work in self:
            work.evidence_count = len(work.evidence_ids)

    def action_view_evidences(self):
        """Ver evidencias de la obra."""
        self.ensure_one()
        return {
            'name': _('Evidencias'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.work.evidence',
            'view_mode': 'list,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }





    @api.depends('budget_total', 'amount_committed', 'amount_paid')
    def _compute_financial_progress(self):
        """Calcula el avance financiero: (Pagado + Comprometido) / Presupuesto Total GLOBAL."""
        for work in self:
            # Siempre usar el total GLOBAL para avance financiero
            all_budgets = work.budget_ids.filtered(
                lambda b: b.state in ('validated', 'consolidated')
            )
            global_total = sum(all_budgets.mapped('total_amount'))
            
            if global_total > 0:
                work.financial_progress = (
                    (work.amount_paid + work.amount_committed) / global_total
                ) * 100
            else:
                work.financial_progress = 0.0

    @api.depends('overall_progress', 'financial_progress')
    def _compute_consistency_warning(self):
        """Detecta si el avance financiero supera al físico."""
        for work in self:
            work.consistency_warning = work.financial_progress > work.overall_progress

    # === MÉTODOS DE ALERTAS ===

    # === ACCIONES DEL DASHBOARD ===
    def action_view_committed(self):
        """Ver partidas que contribuyen al comprometido (distribuido > 0)."""
        self.ensure_one()
        budgets = self._get_selected_budget()
        # Si budgets está vacío, usar _get_active_budget para no romper contexto
        # Aunque si está vacío no habrá partidas.
        if not budgets:
             budget = self._get_active_budget() # Fallback compatible
             budgets = budget
        
        return {
            'name': _('Comprometido (Partidas Distribuidas)'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            'domain': [('budget_id', 'in', budgets.ids), ('total_distributed', '>', 0)],
            'context': {'default_budget_id': budgets[0].id if budgets else False},
        }

    def action_view_paid(self):
        """Ver gastos reales (Pagado)."""
        self.ensure_one()
        return {
            'name': _('Pagado (Gastos Reales)'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.real.line',
            'view_mode': 'list,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }

    def action_view_available(self):
        """Ver partidas con saldo disponible por distribuir."""
        self.ensure_one()
        budgets = self._get_selected_budget()
        if not budgets:
             budget = self._get_active_budget()
             budgets = budget

        return {
            'name': _('Disponible (Por Distribuir)'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            'domain': [('budget_id', 'in', budgets.ids), ('amount_undistributed', '>', 0)],
            'context': {'default_budget_id': budgets[0].id if budgets else False},
        }

    def action_view_budget(self):
        """Abre la lista de presupuestos de la obra."""
        self.ensure_one()
        return {
            'name': _('Presupuestos - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget',
            'view_mode': 'list,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }


    def action_open_consolidate_wizard(self):
        """Abre wizard para consolidar presupuestos de la obra."""
        self.ensure_one()
        # Verificar que hay presupuestos validados
        validated = self.budget_ids.filtered(
            lambda b: b.state == 'validated' and b.budget_type != 'consolidated'
        )
        if len(validated) < 2:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No hay suficientes presupuestos'),
                    'message': _('Necesita al menos 2 presupuestos validados para consolidar.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        return {
            'name': _('Consolidar Presupuestos'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.consolidate.budget.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_work_id': self.id},
        }

    def action_register_progress(self):
        """Abre wizard para registrar avance en una etapa."""
        self.ensure_one()
        return {
            'name': _('Registrar Avance'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.work.stage',
            'view_mode': 'list,form',
            'domain': [('work_id', '=', self.id)],
            'context': {'default_work_id': self.id},
        }

    def action_request_purchase(self):
        """Acción placeholder para solicitar compra."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Solicitar Compra'),
                'message': _('Flujo de compras en desarrollo (MVP). Integración con módulo purchase pendiente.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_ai_assistant(self):
        """Abre el wizard de configuración del Asistente IA."""
        self.ensure_one()
        return {
            'name': _('Asistente IA — Configuración'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.ai.config.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_work_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }
    def action_set_planning(self):
        """
        Transición a Planeación.
        Se llama automáticamente al validar el primer presupuesto.
        """
        for work in self:
            if work.state == 'draft':
                work.write({'state': 'planning'})
                work.message_post(body=_("La obra ha pasado a etapa de Planeación."))

    def action_start_execution(self):
        """
        Inicia la ejecución de la obra.
        Botón manual para pasar de Planning a Running.
        """
        for work in self:
            if work.state == 'planning':
                work.write({'state': 'running'})
                work.message_post(body=_("La ejecución de la obra ha comenzado 🚀"))

    def _check_completion(self):
        """
        Verifica si la obra puede cerrarse automáticamente.
        Se llama cuando se cierra una etapa.
        """
        for work in self:
            if work.state == 'running':
                # Si no tiene etapas activas, ni por aprobar, ni planeadas
                # Es decir, todas las etapas están 'done'
                active_stages = work.stage_ids.filtered(lambda s: s.state != 'done')
                if not active_stages and work.stage_ids:
                    work.write({'state': 'done'})
                    work.message_post(body=_("¡Todas las etapas han concluido! La obra ha sido marcada como Finalizada."))
