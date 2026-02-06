# -*- coding: utf-8 -*-
"""
Modelo: Partida de Presupuesto (building.budget.line)
Línea individual del presupuesto con importe y distribución por periodos.
"""

from odoo import models, fields, api, _
from odoo.models import UniqueIndex
from odoo.exceptions import UserError


class BuildingBudgetLine(models.Model):
    """
    Partida de Presupuesto.
    Representa un concepto específico con importe y distribución temporal.
    """
    _name = 'building.budget.line'
    _description = 'Partida de Presupuesto'
    _order = 'chapter_id, sequence, code'

    # === CONSTRAINTS (Odoo 19 Style) ===
    _unique_stage_base_line = UniqueIndex(
        '(stage_id, base_budget_line_id)',
        message='¡Esta partida del presupuesto ya está asignada a esta etapa! No se permiten duplicados.'
    )
    _unique_budget_chapter_code = UniqueIndex(
        '(budget_id, chapter_id, code)',
        message='¡El código de partida debe ser único por capítulo en este presupuesto!'
    )

    # === CAMPOS BÁSICOS ===
    base_budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida Base',
        help='Partida original del presupuesto de obra (si esta línea es una asignación).',
        ondelete='set null',
        copy=False,
        index=True
    )
    chapter_id = fields.Many2one(
        'building.budget.chapter',
        string='Capítulo',
        required=True,
        ondelete='cascade',
        index=True
    )

    code = fields.Char(
        string='Código',
        required=True,
        help='Código de la partida (1, 2, 3...)'
    )

    name = fields.Char(
        string='Concepto',
        required=True,
        help='Descripción del concepto'
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización'
    )

    # === CAMPOS MONETARIOS ===
    amount = fields.Float(
        string='Importe',
        default=0.0,
        help='Importe total de la partida'
    )

    advance = fields.Float(
        string='Anticipo',
        default=0.0,
        help='Monto de anticipo'
    )

    # === CAMPOS DE DISTRIBUCIÓN POR PERÍODOS ===
    period_from = fields.Integer(
        string='Desde Período',
        default=1,
        help='Período inicial para la distribución (M1, M2, etc.)'
    )

    period_to = fields.Integer(
        string='Hasta Período',
        compute='_compute_period_to_default',
        store=True,
        readonly=False,
        help='Período final para la distribución'
    )

    # === CAMPOS RELACIONADOS ===
    budget_id = fields.Many2one(
        related='chapter_id.budget_id',
        store=True,
        readonly=True,
        index=True
    )

    work_id = fields.Many2one(
        related='chapter_id.work_id',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related='chapter_id.currency_id',
        store=True,
        readonly=True
    )

    state = fields.Selection(
        related='budget_id.state',
        store=True,
        readonly=True
    )

    duration_months = fields.Integer(
        related='budget_id.duration_months',
        readonly=True
    )

    chapter_code = fields.Char(
        related='chapter_id.code',
        string='Cap.',
        readonly=True
    )

    # === RELACIONES ===
    period_value_ids = fields.One2many(
        'building.budget.period.value',
        'line_id',
        string='Valores por Periodo'
    )

    # === CAMPOS COMPUTADOS (stored) ===
    total_distributed = fields.Float(
        string='Total Distribuido',
        compute='_compute_distribution',
        store=True,
        help='Suma de valores en todos los periodos'
    )

    amount_undistributed = fields.Float(
        string='Por Distribuir',
        compute='_compute_distribution',
        store=True,
        help='Importe - Total Distribuido'
    )

    difference = fields.Float(
        string='Diferencia',
        compute='_compute_distribution',
        store=True,
        help='Importe - Total Distribuido'
    )

    has_warning = fields.Boolean(
        string='Advertencia',
        compute='_compute_distribution',
        store=True,
        help='True si hay diferencia entre importe y distribuido'
    )

    # === CAMPO COMPUTADO (no stored, método separado) ===
    warning_message = fields.Char(
        string='Mensaje',
        compute='_compute_warning_message',
        help='Mensaje de advertencia si aplica'
    )

    # === FASE 3.3: AVANCE FÍSICO POR PARTIDA ===
    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa / Frente',
        domain="[('work_id', '=', work_id)]",
        help='Etapa a la que pertenece esta partida para fines de avance físico.',
        index=True
    )

    physical_progress = fields.Float(
        string='Avance Físico (%)',
        default=0.0,
        readonly=True, # Gestionado por Engine
        help='Avance real acumulado (0-100%). Calculado por Progress Engine.'
    )

    executed_amount = fields.Float(
        string='Monto Ejecutado',
        default=0.0,
        readonly=True, # Gestionado por Engine
        help='Importe * (Avance Físico / 100)'
    )

    progress_ids = fields.One2many(
        'building.budget.progress',
        'line_id',
        string='Historial de Avance'
    )

    last_progress_date = fields.Date(
        string='Último Avance',
        readonly=True
    )
    
    last_progress_user_id = fields.Many2one(
        'res.users',
        string='Reportado por',
        readonly=True
    )

    # === FASE 3.3.2: SEMÁFORO FINANCIERO POR PARTIDA ===
    real_line_ids = fields.One2many(
        'building.real.line',
        'budget_line_id',
        string='Gastos Reales',
        help='Registros de gastos reales asociados a esta partida'
    )

    real_total = fields.Monetary(
        string='Gasto Real',
        compute='_compute_financial_data',
        store=True,
        currency_field='currency_id',
        help='Suma total de gastos reales aprobados'
    )

    variance_amount = fields.Monetary(
        string='Desviación',
        compute='_compute_financial_data',
        store=True,
        currency_field='currency_id',
        help='Diferencia: Presupuesto - Gasto Real. Negativo indica sobrecosto.'
    )

    consume_pct = fields.Float(
        string='% Consumo',
        compute='_compute_financial_data',
        store=True,
        aggregator="avg",
        help='Porcentaje del presupuesto consumido (Real / Presupuesto)'
    )

    traffic_light = fields.Selection([
        ('green', 'En Presupuesto'),
        ('yellow', 'Precaución'),
        ('red', 'Excedido'),
    ], string='Semáforo', compute='_compute_financial_data', store=True)

    @api.depends('amount', 'real_line_ids.amount', 'work_id.real_source')
    def _compute_financial_data(self):
        """
        Calcula métricas financieras y semáforo.
        Utiliza building.financial.engine para lógica centralizada.
        """
        Engine = self.env['building.financial.engine']
        
        # Obtener umbrales desde configuración (o defaults)
        ICP = self.env['ir.config_parameter'].sudo()
        thresh_warn = float(ICP.get_param('building.budget_real_threshold_warning', 90.0))
        thresh_crit = float(ICP.get_param('building.budget_real_threshold_critical', 100.0))

        for line in self:
            # 1. Calcular Real (Delegar a lógica simple o motor si fuera complejo)
            # Como tenemos real_line_ids, podemos sumar directo si "internal".
            # Pero para consistencia con filtros de 'work.real_source', usamos el engine si es posible,
            # o replicamos lógica simple aquí si el engine opera en batch.
            # Para eficiencia en listados grandes, sumamos directo de la relación filtrando lo necesario.
            
            # NOTA: Si la fuente es 'accounting', esto podría requerir lógica más compleja.
            # Por ahora asumimos fuente interna o contable mapeada en real_line_ids.
            
            # Suma simple de líneas reales (el motor ya filtra al crear/consultar, 
            # pero aquí accedemos a la BD directamente para store=True).
            # TODO: Refinar si real_source cambia dinámicamente.
            
            real = sum(line.real_line_ids.filtered(lambda r: not r.is_migrated).mapped('amount'))
            # Nota: la logica de 'is_migrated' depende de si estamos leyendo de contabilidad o no.
            # Si work.real_source == 'internal', sumamos todo. 
            # Si work.real_source == 'accounting', sumamos account.move.line (v2).
            
            # Simplificación Fase 3.3.2: Usamos sum(amount) de real_line_ids presentes.
            # El Financial Engine debe encargarse de popular/leer real_line_ids correctamente.
            real = sum(line.real_line_ids.mapped('amount'))

            line.real_total = real
            line.variance_amount = line.amount - real
            
            # 2. Calcular % Consumo
            if line.amount > 0:
                line.consume_pct = (real / line.amount) * 100.0
            else:
                line.consume_pct = 0.0 if real == 0 else 999.0 # Presupuesto 0 con gasto = infinito
            
            # 3. Calcular Semáforo
            line.traffic_light = Engine.get_traffic_light(
                line.amount, real,
                threshold_warning=thresh_warn,
                threshold_critical=thresh_crit
            )

    # === DISPLAY NAME ===
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    # === MÉTODOS COMPUTE ===
    @api.depends('budget_id.duration_months')
    def _compute_period_to_default(self):
        """Establece el período final por defecto igual a la duración del presupuesto."""
        for line in self:
            if line.budget_id and line.budget_id.duration_months:
                line.period_to = line.budget_id.duration_months
            else:
                line.period_to = 12

    @api.depends('period_value_ids', 'period_value_ids.amount', 'amount', 'advance')
    def _compute_distribution(self):
        """Calcula totales de distribución y detecta advertencias."""
        for line in self:
            line.total_distributed = sum(line.period_value_ids.mapped('amount'))
            line.amount_undistributed = line.amount - line.total_distributed
            
            # La diferencia debe considerar el anticipo (se resta del importe total)
            distributable = line.amount - line.advance
            line.difference = distributable - line.total_distributed
            line.has_warning = abs(line.difference) > 0.01

    @api.depends('has_warning', 'difference')
    def _compute_warning_message(self):
        """Genera mensaje de advertencia (campo no almacenado)."""
        for line in self:
            if line.has_warning:
                line.warning_message = _('⚠ Diferencia: %.2f') % line.difference
            else:
                line.warning_message = False

    @api.depends('code', 'name', 'chapter_id.code')
    def _compute_display_name(self):
        """Genera nombre para mostrar."""
        for line in self:
            if line.chapter_id:
                line.display_name = f"{line.chapter_id.code}.{line.code} {line.name}"
            else:
                line.display_name = f"{line.code} {line.name}"

    # === ONCHANGE ===
    @api.onchange('name')
    def _onchange_name_titlecase(self):
        """Convierte el concepto a Title Case (Primera Letra Mayúscula) y normaliza espacios."""
        if self.name:
            self.name = self._normalize_concept(self.name)

    @api.onchange('code')
    def _onchange_code_normalize(self):
        """Normaliza código a Mayúsculas."""
        if self.code:
            self.code = self._normalize_code(self.code)

    # === NORMALIZATION HELPERS (R2, R3) ===
    def _normalize_code(self, code):
        """R2: Upper + Trim."""
        return code.strip().upper() if code else False

    def _normalize_concept(self, name):
        """R3: Title Case + Trim + Collapsed Spaces."""
        if not name:
            return False
        # split() sin argumentos divide por cualquier whitespace y elimina vacios
        return " ".join(name.strip().split()).title()

    # === CRUD OVERRIDES ===
    @api.model_create_multi
    def create(self, vals_list):
        """Bloquea creación si el presupuesto está validado.
        
        También fuerza recálculo de KPIs en building.work.
        Aplica normalización (R2, R3).
        """
        for vals in vals_list:
            # Normalización
            if vals.get('code'):
                vals['code'] = vals['code'].strip().upper()
            
            if vals.get('name'):
                vals['name'] = " ".join(vals['name'].strip().split()).title()

            chapter_id = vals.get('chapter_id')
            if chapter_id:
                chapter = self.env['building.budget.chapter'].browse(chapter_id)
                if chapter.budget_id.state == 'validated' and not self.env.context.get('allow_stage_assignment_on_validated'):
                    raise UserError(_(
                        'No se pueden agregar partidas a un presupuesto validado.\n'
                        'Primero debe reabrir el presupuesto.'
                    ))
        
        records = super().create(vals_list)
        
        # Forzar recálculo de KPIs en la obra
        works = records.mapped('work_id')
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
                # ENGINE: Lineas nuevas empiezan en 0, pero si tienen stage
                # podrían afectar el promedio ponderedo (ahora más monto total).
                self.env['building.progress.engine'].recompute_hierarchy(work.id)
        
        return records

    def unlink(self):
        """Bloquea eliminación si el presupuesto está validado.
        
        También fuerza recálculo de KPIs en building.work.
        """
        works = self.mapped('work_id')
        
        for line in self:
            if line.state == 'validated' and not self.env.context.get('allow_stage_assignment_on_validated'):
                 # Allow unlink if context is set (e.g. migration tools), otherwise block.
                raise UserError(_(
                    'No se pueden eliminar partidas de un presupuesto validado.\n'
                    'Primero debe reabrir el presupuesto.'
                ))
            # Regla de borrado Fase F:
            if line.work_id.state == 'in_progress' and line.state != 'draft':
                 pass # Se permiten borrar si no validado? UserError arriba lo cubre.
                 # User request: "Permitido SOLO si project.state != 'in_process'" (running)
            if line.physical_progress > 0:
                raise UserError(_(
                    'No se puede eliminar la partida "%s" porque tiene un avance del %.2f%%.\n'
                    'Debe cancelar los avances registrados antes de eliminarla.'
                ) % (line.name, line.physical_progress))
            
            if line.work_id.state == 'running':
                 raise UserError(_('No se pueden eliminar partidas de una obra en ejecución.'))

        
        result = super().unlink()
        
        # Forzar recálculo después de eliminar
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
                # ENGINE: Recalcular pesos
                self.env['building.progress.engine'].recompute_hierarchy(work.id)
        
        return result

    def write(self, vals):
        """Bloquea edición de campos importantes si el presupuesto está validado.
        
        También fuerza recálculo de KPIs en building.work.
        Aplica Normalización (R2, R3).
        """
        # Normalización
        if type(vals) == dict: # Defensive
            if vals.get('code'):
                vals['code'] = vals['code'].strip().upper()
            if vals.get('name'):
                vals['name'] = " ".join(vals['name'].strip().split()).title()

        # Campos protegidos cuando el presupuesto está validado
        if self.filtered(lambda l: l.state == 'validated'):
             # Se permite escribir SIEMPRE si el contexto lo autoriza (ej. Wizard de Carga o Migración)
             if not self.env.context.get('allow_stage_assignment_on_validated'):
                 # Lista detallada de campos criticos
                 # Permitimos Sequence para reordenar? Si.
                 # Permitimos Period_To para ajustar cronograma? Hmm, eso afecta flujo. Bloqueamos por defecto.
                 # stage_id se permite cambiar AUNQUE no tenga context?
                 # USER REQUEST: "Debe permitir asignar/reasignar stage_id aunque el presupuesto esté cerrado."
                 # Entonces stage_id NO debe estar en restricted si cambiamos SOLO stage_id.
                 
                 for line in self:
                     # Check which fields are being modified
                     modified_fields = vals.keys()
                     
                     # Campos estrictamente prohibidos
                     restricted = ['amount', 'code', 'name', 'chapter_id', 'period_from', 'period_to', 'currency_id']
                     
                     # Si se intenta tocar alguno de los restringidos
                     if any(f in modified_fields for f in restricted):
                         raise UserError(_(
                            'No se pueden modificar datos financieros o estructurales en un presupuesto validado.\n'
                            'Campos bloqueados: %s'
                        ) % ', '.join([f for f in restricted if f in modified_fields]))
        
        # Validación de desvinculación de etapa con avance
        if 'stage_id' in vals and not vals.get('stage_id'):
            # Si se está quitando la etapa (stage_id=False)
            for line in self:
                if line.physical_progress > 0:
                    raise UserError(_(
                        'No se puede desvincular la partida "%s" de su etapa porque tiene avance registrado (%.2f%%).\n'
                        'Debe cancelar los avances antes de moverla o eliminarla de la etapa.'
                    ) % (line.name, line.physical_progress))
        
        result = super().write(vals)
        
        # Forzar recálculo de KPIs en la obra y ENGINE
        engine_needs_update = False
        if 'amount' in vals or 'stage_id' in vals:
            engine_needs_update = True

        for line in self:
            if line.work_id:
                line.work_id._compute_budget_kpis()
                line.work_id._compute_amount_available()
                line.work_id._compute_financial_progress()

                if engine_needs_update:
                     self.env['building.progress.engine'].recompute_hierarchy(
                         line.work_id.id,
                         line_ids=[line.id]
                     )
        
        return result

    # === ACCIONES ===
    def action_distribute_uniform(self):
        """Distribuye el importe uniformemente entre los periodos seleccionados."""
        self.ensure_one()
        if not self.budget_id or self.budget_id.duration_months <= 0:
            return False

        # Validar períodos
        period_from = self.period_from or 1
        period_to = self.period_to or self.budget_id.duration_months
        
        # Asegurar que period_to no exceda la duración
        if period_to > self.budget_id.duration_months:
            period_to = self.budget_id.duration_months
        
        # Asegurar que period_from sea válido
        if period_from < 1:
            period_from = 1
        if period_from > period_to:
            period_from = period_to

        # Eliminar valores existentes
        self.period_value_ids.unlink()

        # Calcular cantidad de períodos a distribuir
        num_periods = period_to - period_from + 1
        
        # Calcular monto por periodo (importe - anticipo)
        distributable = self.amount - self.advance
        amount_per_period = distributable / num_periods if num_periods > 0 else 0

        # Crear valores solo para los periodos seleccionados
        period_vals = []
        for i in range(period_from, period_to + 1):
            period_vals.append({
                'line_id': self.id,
                'period_number': i,
                'amount': amount_per_period,
            })

        self.env['building.budget.period.value'].create(period_vals)
        
        # Recargar el modal para mostrar la distribución
        return self.action_open_distribution()

    def action_clear_distribution(self):
        """Limpia la distribución de periodos."""
        self.ensure_one()
        self.period_value_ids.unlink()
        
        # Recargar el modal para mostrar el cambio
        return self.action_open_distribution()


    def action_open_distribution(self):
        """Abre vista para editar partida y distribución por periodos.
        
        Reutiliza la vista principal building_budget_line_view_form
        que ya incluye todas las funcionalidades de distribución.
        """
        self.ensure_one()
        return {
            'name': _('Partida: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'form',
            'res_id': self.id,
            'view_id': self.env.ref('building_dashboard.building_budget_line_view_form').id,
            'target': 'new',
        }

    def action_save_and_distribute(self):
        """Guarda la partida y abre el modal de distribución."""
        self.ensure_one()
        # Primero distribuir uniformemente
        self.action_distribute_uniform()
        # Luego abrir el modal de distribución
        # Luego abrir el modal de distribución
        return self.action_open_distribution()

    def action_register_progress(self):
        """Abre wizard para registrar avance físico a la partida."""
        self.ensure_one()
        return {
            'name': _('Registrar Avance: %s') % self.code,
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.progress.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_current_accumulated': self.physical_progress,
            },
        }

    @api.model
    def action_create_popup(self):
        """Abre formulario para crear nueva partida como popup.
        
        Este método se llama desde el botón en el header de la lista
        para abrir el formulario de creación en modo popup.
        Reutiliza la misma vista building_budget_line_view_form.
        """
        # Obtener chapter_id del contexto si existe
        chapter_id = self.env.context.get('default_chapter_id')
        
        ctx = dict(self.env.context)
        if chapter_id:
            chapter = self.env['building.budget.chapter'].browse(chapter_id)
            # Generar código siguiente
            existing_count = len(chapter.line_ids)
            ctx['default_code'] = str(existing_count + 1)
            ctx['default_sequence'] = (existing_count + 1) * 10
        
        return {
            'name': _('Nueva Partida'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'form',
            'view_id': self.env.ref('building_dashboard.building_budget_line_view_form').id,
            'target': 'new',
            'context': ctx,
        }
