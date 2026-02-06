# -*- coding: utf-8 -*-
"""
Modelo: Presupuesto de Obra (building.budget)
Entidad principal del presupuesto paramétrico.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BuildingBudget(models.Model):
    """
    Presupuesto de Obra.
    Contiene capítulos y partidas con distribución por periodos.
    """
    _name = 'building.budget'
    _description = 'Presupuesto de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create para validar estado de la obra."""
        for vals in vals_list:
            if vals.get('work_id'):
                work = self.env['building.work'].browse(vals['work_id'])
                if work.state == 'done':
                    raise UserError(_('No se puede crear un presupuesto para una obra finalizada.'))
        return super().create(vals_list)

    # === CAMPOS BÁSICOS ===
    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
        default=lambda self: _('Nuevo Presupuesto'),
        help='Nombre identificador del presupuesto'
    )

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Obra a la que pertenece este presupuesto'
    )

    company_id = fields.Many2one(
        related='work_id.company_id',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related='work_id.currency_id',
        store=True,
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('validated', 'Validado'),
    ], string='Estado', default='draft', required=True, tracking=True)

    # === VERSIONADO (R1) ===
    version_no = fields.Integer(
        string='Versión No.',
        default=0,
        copy=False,
        tracking=True,
        help='Número de versión del presupuesto (se incrementa al validar)'
    )
    
    version_label = fields.Char(
        string='Versión',
        compute='_compute_version_label',
        store=True,
        help='Etiqueta de versión (V1, V2...)'
    )

    @api.depends('version_no')
    def _compute_version_label(self):
        for budget in self:
            budget.version_label = f"V{budget.version_no}" if budget.version_no > 0 else "Borrador"

    # === CAMPOS DE REAPERTURA ===
    reopened_by = fields.Many2one(
        'res.users',
        string='Reabierto por',
        readonly=True,
        help='Usuario que reabrió el presupuesto'
    )
    reopened_date = fields.Datetime(
        string='Fecha Reapertura',
        readonly=True,
        help='Fecha y hora de la última reapertura'
    )

    # === CONFIGURACIÓN DE PERIODOS ===
    duration_months = fields.Integer(
        string='Duración (meses)',
        default=12,
        required=True,
        help='Número de periodos (M1, M2, ..., MN) para distribución'
    )

    # === RELACIONES ===
    chapter_ids = fields.One2many(
        'building.budget.chapter',
        'budget_id',
        string='Capítulos'
    )

    # === CAMPOS COMPUTADOS ===
    total_amount = fields.Monetary(
        string='Presupuesto Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de todos los importes de partidas'
    )

    total_distributed = fields.Monetary(
        string='Total Distribuido',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de todos los valores distribuidos en periodos'
    )

    total_advance = fields.Monetary(
        string='Total Anticipos',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de todos los anticipos de partidas'
    )

    difference = fields.Monetary(
        string='Diferencia',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Diferencia entre (presupuesto - anticipos) y distribuido'
    )

    has_warning = fields.Boolean(
        string='Tiene Advertencia',
        compute='_compute_totals',
        store=True,
        help='True si hay diferencia entre importe y distribuido'
    )

    chapter_count = fields.Integer(
        string='# Capítulos',
        compute='_compute_chapter_count'
    )

    line_count = fields.Integer(
        string='# Partidas',
        compute='_compute_line_count'
    )

    # === MÉTODOS COMPUTE ===
    @api.depends('chapter_ids', 'chapter_ids.total_amount', 'chapter_ids.total_advance', 'chapter_ids.total_distributed')
    def _compute_totals(self):
        """Calcula totales del presupuesto.
        
        Diferencia = Total - Anticipos - Distribuido
        Si la diferencia es 0, significa que todo está correctamente distribuido.
        """
        for budget in self:
            budget.total_amount = sum(budget.chapter_ids.mapped('total_amount'))
            budget.total_advance = sum(budget.chapter_ids.mapped('total_advance'))
            budget.total_distributed = sum(budget.chapter_ids.mapped('total_distributed'))
            # Fórmula corregida: restar anticipos del total antes de comparar con distribuido
            distributable = budget.total_amount - budget.total_advance
            budget.difference = distributable - budget.total_distributed
            budget.has_warning = abs(budget.difference) > 0.01

    @api.depends('chapter_ids')
    def _compute_chapter_count(self):
        """Cuenta capítulos."""
        for budget in self:
            budget.chapter_count = len(budget.chapter_ids)

    @api.depends('chapter_ids.line_ids')
    def _compute_line_count(self):
        """Cuenta partidas totales."""
        for budget in self:
            budget.line_count = sum(len(ch.line_ids) for ch in budget.chapter_ids)

    # === ACCIONES DE ESTADO ===
    def action_validate(self):
        """Valida el presupuesto con verificaciones.
        
        Validaciones:
        - Debe tener al menos una partida
        - Cada partida debe tener importe > 0
        - Si hay diferencia en distribución, muestra advertencia (no bloquea)
        """
        self.ensure_one()
        if self.state == 'validated':
            raise UserError(_('El presupuesto ya está validado.'))
        
        # Validar que existan partidas
        if self.line_count == 0:
            raise UserError(_('No se puede validar un presupuesto sin partidas.'))
        
        # Validar que cada partida tenga importe
        lines_without_amount = []
        for chapter in self.chapter_ids:
            for line in chapter.line_ids:
                if not line.amount or line.amount <= 0:
                    lines_without_amount.append(f"[{chapter.code}] {line.code} - {line.name}")
        
        if lines_without_amount:
            lines_list = '\n'.join(lines_without_amount[:5])
            if len(lines_without_amount) > 5:
                lines_list += f'\n... y {len(lines_without_amount) - 5} más'
            raise UserError(_(
                'Las siguientes partidas no tienen importe:\n%s'
            ) % lines_list)
        
        # Incrementar versión (R1)
        self.version_no += 1
        
        # Cambiar estado
        self.write({'state': 'validated'})
        
        # Regenerar alertas de la obra (FASE 3.1)
        if self.work_id:
            self.env['building.alert.engine'].rebuild_alerts(self.work_id.id)
            # FASE 7: Transición automática de Obra a Planeación
            self.work_id.action_set_planning()
        
        # Mensaje de éxito con advertencia si hay diferencia
        message = _('Presupuesto validado correctamente.')
        msg_type = 'success'
        
        if self.has_warning:
            message += _(' ⚠️ Advertencia: hay una diferencia de %s pendiente de distribuir.') % (
                self.currency_id.symbol + ' ' + '{:,.2f}'.format(self.difference)
            )
            msg_type = 'warning'
            
        # Chatter Tracking (R1)
        tracking_msg = _(
            "Presupuesto cerrado: V%s — Total: %s — Distribuido: %s — Diferencia: %s"
        ) % (
            self.version_no,
            self.currency_id.symbol + ' ' + '{:,.2f}'.format(self.total_amount),
            self.currency_id.symbol + ' ' + '{:,.2f}'.format(self.total_distributed),
            self.currency_id.symbol + ' ' + '{:,.2f}'.format(self.difference)
        )
        self.message_post(body=tracking_msg, message_type='notification')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Presupuesto Validado'),
                'message': message,
                'type': msg_type,
                'sticky': msg_type == 'warning',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'building.budget',
                    'res_id': self.id,
                    'views': [(False, 'form')],
                    'target': 'main',
                },
            }
        }

    def action_set_draft(self):
        """Reabre el presupuesto (solo Director de Obra).
        
        Registra quién y cuándo reabrió el presupuesto.
        """
        self.ensure_one()
        
        # Verificar permisos - solo Director de Obra puede reabrir
        if not self.env.user.has_group('building_dashboard.group_building_director'):
            raise UserError(_(
                'Solo el Director de Obra puede reabrir un presupuesto validado.'
            ))
        
        # Registrar reapertura
        self.write({
            'state': 'draft',
            'reopened_by': self.env.user.id,
            'reopened_date': fields.Datetime.now(),
        })
        
        # Mensaje en chatter
        self.message_post(
            body=_('Presupuesto reabierto por %s') % self.env.user.name,
            message_type='notification',
        )
        
        # Regenerar alertas de la obra (FASE 3.1)
        if self.work_id:
            self.env['building.alert.engine'].rebuild_alerts(self.work_id.id)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Presupuesto Reabierto'),
                'message': _('El presupuesto ha sido reabierto y puede ser editado.'),
                'type': 'info',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'building.budget',
                    'res_id': self.id,
                    'views': [(False, 'form')],
                    'target': 'main',
                },
            }
        }

    def action_add_chapter(self):
        """Abre wizard para agregar capítulo."""
        self.ensure_one()
        
        # Detectar patrón de códigos existentes y generar el siguiente
        existing_codes = self.chapter_ids.mapped('code')
        next_code = self._get_next_chapter_code(existing_codes)
        
        return {
            'name': _('Nuevo Capítulo'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.chapter',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_budget_id': self.id,
                'default_code': next_code,
                'default_sequence': (len(existing_codes) + 1) * 10,
            },
        }

    def _get_next_chapter_code(self, existing_codes):
        """
        Detecta el patrón de códigos (letras o números) y genera el siguiente.
        - Si son letras (A, B, C...): genera la siguiente letra
        - Si son números (1, 2, 3...): genera el siguiente número
        - Si está vacío: empieza con 'A'
        """
        if not existing_codes:
            return 'A'
        
        # Ordenar códigos
        sorted_codes = sorted(existing_codes)
        last_code = sorted_codes[-1]
        
        # Verificar si el último código es un número
        if last_code.isdigit():
            return str(int(last_code) + 1)
        
        # Verificar si es una letra
        if last_code.isalpha() and len(last_code) == 1:
            next_char = chr(ord(last_code.upper()) + 1)
            # Si pasamos de Z, ir a AA, AB, etc.
            if next_char > 'Z':
                return 'AA'
            return next_char
        
        # Código alfanumérico complejo - solo incrementar cantidad
        return str(len(existing_codes) + 1)


    def action_add_line(self):
        """Abre wizard para agregar partida (desde el presupuesto)."""
        self.ensure_one()
        if not self.chapter_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin Capítulos'),
                    'message': _('Primero debe crear al menos un Capítulo antes de agregar Partidas.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Nueva Partida'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_budget_id': self.id,
                # Pre-seleccionar el último capítulo
                'default_chapter_id': self.chapter_ids[-1].id if self.chapter_ids else False,
            },
        }


    def action_distribute_all(self):
        """Distribuye uniformemente todos los importes."""
        self.ensure_one()
        for chapter in self.chapter_ids:
            for line in chapter.line_ids:
                line.action_distribute_uniform()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Distribución Completada'),
                'message': _('Se distribuyeron uniformemente %d partidas.') % self.line_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_chapters(self):
        """Ver capítulos del presupuesto."""
        self.ensure_one()
        return {
            'name': _('Capítulos'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.chapter',
            'view_mode': 'list,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id},
        }

    def action_view_lines(self):
        """Ver todas las partidas del presupuesto."""
        self.ensure_one()
        return {
            'name': _('Partidas'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            'domain': [('budget_id', '=', self.id)],
            'context': {'default_budget_id': self.id},
        }

    def action_view_difference_lines(self):
        """Ver partidas con diferencia (Undistributed != 0)."""
        self.ensure_one()
        return {
            'name': _('Partidas con Diferencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            # Usamos float_compare o rango para evitar problemas de redondeo, o un campo computado boolean
            'domain': [('budget_id', '=', self.id), ('has_warning', '=', True)],
            'context': {'default_budget_id': self.id},
        }

    def action_view_exceeded_lines(self):
        """Ver partidas excedidas (Semáforo Rojo o Amarillo)."""
        self.ensure_one()
        return {
            'name': _('Partidas Excedidas'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            'domain': [('budget_id', '=', self.id), ('traffic_light', 'in', ['red', 'yellow'])],
            'context': {'default_budget_id': self.id},
        }

    # === SINCRONIZACIÓN CON OBRA ===
    def write(self, vals):
        """Override write para forzar recálculo de KPIs en building.work."""
        # FASE 7: Bloquear edición si la obra está finalizada
        for budget in self:
            if budget.work_id.state == 'done':
                raise UserError(_('No se puede modificar el presupuesto de una obra finalizada.'))

        result = super().write(vals)
        # Forzar recálculo de KPIs en la obra después de cualquier cambio
        for budget in self:
            if budget.work_id:
                budget.work_id._compute_budget_kpis()
                budget.work_id._compute_amount_available()
                budget.work_id._compute_financial_progress()
        return result

    # === DATA MIGRATION / CLEANUP (HARDENING 0 -> 3.3.2) ===
    def action_consolidate_assigned_lines(self):
        """
        Herramienta de migración para eliminar duplicados "Base vs Asignada".
        Consolida la información de las líneas asignadas (Etapa, Avance, Gastos)
        hacia la línea base original y elimina la copia.
        """
        self.ensure_one()
        
        # Buscar duplicados (líneas que apuntan a una base) dentro de este presupuesto
        # Nota: Buscamos en todas las lineas del presupuesto que tengan base_budget_line_id
        duplicates = self.env['building.budget.line'].search([
            ('budget_id', '=', self.id),
            ('base_budget_line_id', '!=', False)
        ])
        
        if not duplicates:
             return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nada que consolidar'),
                    'message': _('No se encontraron líneas duplicadas (con base_line definida) en este presupuesto.'),
                    'type': 'info',
                }
            }

        Stats = {'merged': 0, 'errors': 0}
        
        # Iterar y fusionar
        for assigned in duplicates:
            base = assigned.base_budget_line_id
            if not base:
                continue # Edge case, base deleted?
            
            try:
                # 1. Transferir ETAPA
                # Si la asignada tiene etapa y la base no (o si priorizamos la asignada), pasarla.
                if assigned.stage_id:
                    base.stage_id = assigned.stage_id
                
                # 2. Transferir AVANCES (Progress History)
                if assigned.progress_ids:
                    assigned.progress_ids.write({'line_id': base.id})
                    # Recalcular Base
                    # (El engine lo hará al final o podemos forzar recompute)
                
                # 3. Transferir GASTOS REALES (Real Lines)
                if assigned.real_line_ids:
                    assigned.real_line_ids.write({'budget_line_id': base.id})
                
                # 4. Transferir DISTRIBUCION (Period Values)
                # Asumimos que la asignada tiene la distribución "viva".
                if assigned.period_value_ids:
                    base.period_value_ids.unlink() # Borrar la de la base
                    assigned.period_value_ids.write({'line_id': base.id}) # Mover la asignada
                
                # 5. Borrar duplicado
                # Antes de borrar, debemos resetear el avance físico en la línea asignada
                # para que no salte el constraint "No se puede eliminar... si tiene avance".
                # Como ya movimos los progress_ids, el avance lógico es 0, pero el campo stored
                # necesita ser actualizado manualmente o forzado.
                assigned.with_context(allow_stage_assignment_on_validated=True).write({
                    'physical_progress': 0, 
                    'executed_amount': 0
                })
                
                # Forzamos borrado incluso si validado (Context override)
                assigned.with_context(allow_stage_assignment_on_validated=True).unlink()
                
                Stats['merged'] += 1
                
            except Exception as e:
                Stats['errors'] += 1
                # Log error
        
        # Recomputar todo el presupuesto
        self.flush_model()
        self.chapter_ids.mapped('line_ids')._compute_financial_data()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Consolidación Completa'),
                'message': _('Se fusionaron %s líneas duplicadas. Errores: %s') % (Stats['merged'], Stats['errors']),
                'type': 'success',
            }
        }
