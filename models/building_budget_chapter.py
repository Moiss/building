# -*- coding: utf-8 -*-
"""
Modelo: Capítulo de Presupuesto (building.budget.chapter)
Agrupa partidas del presupuesto por categoría.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BuildingBudgetChapter(models.Model):
    """
    Capítulo de Presupuesto.
    Agrupa partidas relacionadas (ej: Obra Civil, Estructura, etc.)
    """
    _name = 'building.budget.chapter'
    _description = 'Capítulo de Presupuesto'
    _order = 'sequence, code'

    @api.model
    def default_get(self, fields_list):
        """Genera código y secuencia consecutivos automáticamente."""
        defaults = super().default_get(fields_list)
        
        # Obtener budget_id del contexto
        budget_id = self.env.context.get('default_budget_id')
        if budget_id:
            budget = self.env['building.budget'].browse(budget_id)
            existing_chapters = budget.chapter_ids.filtered(lambda c: c.id)
            existing_codes = existing_chapters.mapped('code')
            
            # Generar código consecutivo
            if 'code' in fields_list:
                defaults['code'] = self._get_next_code(existing_codes)
            
            # Generar secuencia consecutiva (10, 20, 30, ...)
            if 'sequence' in fields_list:
                max_sequence = max(existing_chapters.mapped('sequence') or [0])
                defaults['sequence'] = max_sequence + 10
        else:
            if 'code' not in defaults:
                defaults['code'] = 'CAP-01'
            if 'sequence' not in defaults:
                defaults['sequence'] = 10
        
        return defaults

    def _get_next_code(self, existing_codes):
        """
        Genera el siguiente código en secuencia: A, B, C...Z, AA, AB...AZ, BA, BB...
        Similar a las columnas de Excel.
        """
        if not existing_codes:
            return 'CAP-01'
        
        # Extraer números de los códigos existentes que sigan el patrón CAP-XX
        max_num = 0
        for code in existing_codes:
            if code and code.startswith('CAP-'):
                try:
                    num = int(code.split('-')[1])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        
        # Generar el siguiente: CAP-02
        return 'CAP-%02d' % (max_num + 1)
        

        
        # Generar el siguiente
        return num_to_letters(max_num + 1)


    @api.model_create_multi
    def create(self, vals_list):
        """Asegura código consecutivo en creación inline y bloquea si está validado.
        
        También fuerza recálculo de KPIs en building.work.
        """
        for vals in vals_list:
            budget_id = vals.get('budget_id') or self.env.context.get('default_budget_id')
            
            if budget_id:
                budget = self.env['building.budget'].browse(budget_id)
                
                # Bloquear si el presupuesto está validado
                if budget.state == 'validated':
                    raise UserError(_(
                        'No se pueden agregar capítulos a un presupuesto validado.\n'
                        'Primero debe reabrir el presupuesto.'
                    ))
                
                # Obtener códigos existentes (solo de registros guardados)
                existing_codes = budget.chapter_ids.filtered(lambda c: c.id).mapped('code')
                
                proposed_code = vals.get('code', 'CAP-01').upper() if vals.get('code') else 'CAP-01'
                
                # Si el código propuesto ya existe, generar el siguiente
                if proposed_code in existing_codes or not vals.get('code'):
                    vals['code'] = self._get_next_code(existing_codes)
                else:
                    vals['code'] = proposed_code
            
            # Convertir código a mayúsculas
            if vals.get('code'):
                vals['code'] = vals['code'].strip().upper()
            # Convertir nombre a Title Case
            if vals.get('name'):
                vals['name'] = " ".join(vals.get('name').strip().split()).title()
        
        records = super().create(vals_list)
        
        # Forzar recálculo de KPIs en la obra
        works = records.mapped('work_id')
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
        
        return records


    # === CAMPOS BÁSICOS ===
    budget_id = fields.Many2one(
        'building.budget',
        string='Presupuesto',
        required=True,
        ondelete='cascade',
        index=True
    )

    code = fields.Char(
        string='Código',
        required=True,
        default='CAP-01',
        help='Código del capítulo (CAP-XX)'
    )

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo del capítulo'
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de visualización'
    )

    # === CAMPOS RELACIONADOS ===
    work_id = fields.Many2one(
        related='budget_id.work_id',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        related='budget_id.currency_id',
        store=True,
        readonly=True
    )

    state = fields.Selection(
        related='budget_id.state',
        store=True,
        readonly=True
    )

    # === RELACIONES ===
    line_ids = fields.One2many(
        'building.budget.line',
        'chapter_id',
        string='Partidas'
    )

    # === CAMPOS COMPUTADOS ===
    total_amount = fields.Monetary(
        string='Total Importe',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de importes de partidas'
    )

    total_advance = fields.Monetary(
        string='Total Anticipo',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de anticipos de partidas'
    )

    total_distributed = fields.Monetary(
        string='Total Distribuido',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Suma de valores distribuidos en periodos'
    )

    line_count = fields.Integer(
        string='# Partidas',
        compute='_compute_line_count'
    )

    # === DISPLAY NAME ===
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    # === MÉTODOS COMPUTE ===
    @api.depends('line_ids', 'line_ids.amount', 'line_ids.advance', 'line_ids.total_distributed')
    def _compute_totals(self):
        """Calcula totales del capítulo."""
        for chapter in self:
            chapter.total_amount = sum(chapter.line_ids.mapped('amount'))
            chapter.total_advance = sum(chapter.line_ids.mapped('advance'))
            chapter.total_distributed = sum(chapter.line_ids.mapped('total_distributed'))

    @api.depends('line_ids')
    def _compute_line_count(self):
        """Cuenta partidas del capítulo."""
        for chapter in self:
            chapter.line_count = len(chapter.line_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        """Genera nombre para mostrar: [CÓDIGO] Nombre"""
        for chapter in self:
            chapter.display_name = f"[{chapter.code}] {chapter.name}" if chapter.code else chapter.name

    # === ONCHANGE ===
    @api.onchange('name')
    def _onchange_name_titlecase(self):
        """Convierte el nombre del capítulo a Title Case."""
        if self.name:
            self.name = " ".join(self.name.strip().split()).title()

    @api.onchange('code')
    def _onchange_code_uppercase(self):
        """Convierte el código del capítulo a MAYÚSCULAS."""
        if self.code:
            self.code = self.code.strip().upper()

    # === ACCIONES ===
    def action_add_line(self):
        """Abre wizard para agregar partida."""
        self.ensure_one()
        # Generar código siguiente
        existing_count = len(self.line_ids)
        next_code = str(existing_count + 1)
        
        return {
            'name': _('Nueva Partida'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chapter_id': self.id,
                'default_code': next_code,
                'default_sequence': (existing_count + 1) * 10,
            },
        }

    def action_distribute_chapter(self):
        """Distribuye uniformemente todas las partidas del capítulo."""
        self.ensure_one()
        for line in self.line_ids:
            line.action_distribute_uniform()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Distribución Completada'),
                'message': _('Se distribuyeron %d partidas del capítulo %s.') % (
                    len(self.line_ids), self.code
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_lines(self):
        """Abre vista de las partidas del capítulo.
        
        La acción abre la lista con configuración especial que hace que
        al crear o editar una partida se use un popup modal.
        """
        self.ensure_one()
        # Obtener la acción de crear partida en popup
        create_action = self.env.ref('building_dashboard.building_budget_line_action_popup', raise_if_not_found=False)
        
        return {
            'name': _('Partidas: [%s] %s') % (self.code, self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'building.budget.line',
            'view_mode': 'list,form',
            'domain': [('chapter_id', '=', self.id)],
            'context': {
                'default_chapter_id': self.id,
                'dialog_size': 'large',
            },
            'views': [
                (self.env.ref('building_dashboard.building_budget_line_view_list').id, 'list'),
                (self.env.ref('building_dashboard.building_budget_line_view_form').id, 'form'),
            ],
            'target': 'current',
        }

    def unlink(self):
        """Bloquea eliminación si el presupuesto está validado.
        
        También fuerza recálculo de KPIs en building.work.
        """
        works = self.mapped('work_id')
        
        for chapter in self:
            if chapter.state == 'validated':
                raise UserError(_(
                    'No se pueden eliminar capítulos de un presupuesto validado.\n'
                    'Primero debe reabrir el presupuesto.'
                ))
        
        result = super().unlink()
        
        # Forzar recálculo después de eliminar
        for work in works:
            if work:
                work._compute_budget_kpis()
                work._compute_amount_available()
                work._compute_financial_progress()
        
        return result

    def write(self, vals):
        """Bloquea edición de campos importantes si el presupuesto está validado.
        
        También fuerza recálculo de KPIs en building.work.
        """
        # Campos protegidos cuando el presupuesto está validado
        protected_fields = {'name', 'code', 'sequence'}
        fields_to_edit = set(vals.keys())
        
        if fields_to_edit & protected_fields:
            for chapter in self:
                if chapter.state == 'validated':
                    raise UserError(_(
                        'No se pueden modificar capítulos en un presupuesto validado.\n'
                        'Primero debe reabrir el presupuesto.'
                    ))
        
        result = super().write(vals)
        
        # Forzar recálculo de KPIs en la obra
        for chapter in self:
            if chapter.work_id:
                chapter.work_id._compute_budget_kpis()
                chapter.work_id._compute_amount_available()
                chapter.work_id._compute_financial_progress()
        
        return result
