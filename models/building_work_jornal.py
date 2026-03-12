# -*- coding: utf-8 -*-
# Modelos: building.jornal + building.jornal.line
# Registro semanal de mano de obra por trabajador (Fase 4.5)
# worker_id apunta a hr.employee (modelo nativo de Odoo extendido)

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BuildingJornal(models.Model):
    """
    Encabezado de jornal semanal.

    Representa una semana de trabajo en una obra y etapa especifica.
    Contiene los parametros globales de la semana:
    - dias_pagados: cuantos dias se pagan (default 7, semana completa)
    - factor_carga_social: multiplicador por cargas sociales
      (IMSS, Infonavit, Afore, ISN, aguinaldo, vacaciones)
      Default 1.35 = 35% de carga sobre el jornal base.

    Las lineas (building.jornal.line) detallan cada trabajador
    y sus dias reales trabajados esa semana.
    """
    _name = 'building.jornal'
    _description = 'Jornal Semanal de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha_semana desc, id desc'

    # === CAMPOS PRINCIPALES ===

    # Nombre generado automaticamente: "Semana 10/03/2026 — Mi Obra"
    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        help='Nombre generado: Semana DD/MM/YYYY — Obra',
    )

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Obra a la que pertenece este jornal',
    )

    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa / Frente',
        domain="[('work_id', '=', work_id)]",
        tracking=True,
        help='Etapa o frente de obra (opcional)',
    )

    fecha_semana = fields.Date(
        string='Inicio de Semana',
        required=True,
        tracking=True,
        help='Fecha del lunes de la semana que se registra',
    )

    fecha_semana_fin = fields.Date(
        string='Fin de Semana',
        compute='_compute_fecha_semana_fin',
        store=True,
        help='Ultimo dia de la semana (domingo = inicio + 6 dias)',
    )

    numero_semana = fields.Integer(
        string='No. Semana',
        compute='_compute_fecha_semana_fin',
        store=True,
        help='Numero de semana del año segun ISO (1-53)',
    )

    dias_pagados = fields.Integer(
        string='Dias Pagados',
        default=7,
        required=True,
        tracking=True,
        help='Numero de dias que se pagan en la semana. '
             'Default 7 (semana completa incluyendo descanso). '
             'Cambiar si se pagan menos dias.',
    )

    factor_carga_social = fields.Float(
        string='Factor Carga Social',
        default=1.35,
        required=True,
        digits=(4, 2),
        tracking=True,
        help='Multiplicador por cargas sociales sobre el jornal base. '
             'Incluye IMSS, Infonavit, Afore, ISN, aguinaldo, vacaciones. '
             'Default 1.35 = 35%% de carga adicional.',
    )

    # === LINEAS DE TRABAJADORES ===

    line_ids = fields.One2many(
        'building.jornal.line',
        'jornal_id',
        string='Trabajadores',
        help='Detalle de cada trabajador y sus dias trabajados esta semana',
    )

    # === TOTALES CALCULADOS ===

    total_jornal = fields.Float(
        string='Total Jornal',
        compute='_compute_total_jornal',
        store=True,
        help='Suma del costo real (con cargas sociales) de todos los trabajadores',
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='work_id.currency_id',
        store=True,
        readonly=True,
    )

    # === PUENTE FUTURO A GASTOS REALES ===

    real_line_id = fields.Many2one(
        'building.real.line',
        string='Gasto Real Vinculado',
        help='Conexion opcional con el registro de gastos reales (Plan A). '
             'Se usara en fases futuras para integrar jornales al flujo financiero.',
    )

    # === ESTADO Y NOTAS ===

    state = fields.Selection(
        selection=[
            ('borrador', 'Borrador'),
            ('confirmado', 'Confirmado'),
        ],
        string='Estado',
        default='borrador',
        tracking=True,
        help='Borrador: en captura. Confirmado: cerrado para edicion.',
    )

    notes = fields.Text(
        string='Observaciones',
        help='Notas generales de la semana (clima, retrasos, etc.)',
    )

    # === COMPUTE ===

    @api.depends('fecha_semana', 'work_id.name')
    def _compute_name(self):
        """Genera nombre descriptivo: Semana DD/MM/YYYY — Obra"""
        for record in self:
            if record.fecha_semana and record.work_id:
                fecha_str = record.fecha_semana.strftime('%d/%m/%Y')
                record.name = f"Semana {fecha_str} — {record.work_id.name}"
            else:
                record.name = 'Nuevo Jornal'

    @api.depends('fecha_semana')
    def _compute_fecha_semana_fin(self):
        """Calcula el fin de semana (domingo) y el numero de semana ISO"""
        for record in self:
            if record.fecha_semana:
                record.fecha_semana_fin = record.fecha_semana + timedelta(days=6)
                record.numero_semana = record.fecha_semana.isocalendar()[1]
            else:
                record.fecha_semana_fin = False
                record.numero_semana = 0

    @api.depends('line_ids.costo_real')
    def _compute_total_jornal(self):
        """Suma el costo real (con cargas sociales) de todas las lineas"""
        for record in self:
            record.total_jornal = sum(record.line_ids.mapped('costo_real'))

    # === ONCHANGE ===

    @api.onchange('work_id')
    def _onchange_work_id(self):
        """Limpiar etapa si cambia la obra (ya no pertenece)"""
        if self.stage_id and self.stage_id.work_id != self.work_id:
            self.stage_id = False

    # === ACCIONES ===

    def action_confirmar(self):
        """Confirmar el jornal: bloquea edicion"""
        self.write({'state': 'confirmado'})

    def action_borrador(self):
        """Regresar a borrador: permite edicion de nuevo"""
        self.write({'state': 'borrador'})

    # === CONSTRAINTS ===

    @api.constrains('dias_pagados')
    def _check_dias_pagados(self):
        """Validar que los dias pagados esten entre 1 y 7"""
        for record in self:
            if record.dias_pagados < 1 or record.dias_pagados > 7:
                raise ValidationError(
                    _("Los dias pagados deben estar entre 1 y 7.")
                )

    @api.constrains('factor_carga_social')
    def _check_factor_carga(self):
        """El factor de carga social debe ser al menos 1.0 (sin carga = 1.0)"""
        for record in self:
            if record.factor_carga_social < 1.0:
                raise ValidationError(
                    _("El factor de carga social no puede ser menor a 1.0")
                )


class BuildingJornalLine(models.Model):
    """
    Linea de detalle de un jornal semanal.

    Cada linea representa a UN trabajador (hr.employee) en UNA semana.
    El costo se calcula asi:
      costo_directo = dias_pagados (del encabezado) x jornal_base (del empleado)
      costo_real    = costo_directo x factor_carga_social (del encabezado)

    El campo jornal_base se hereda del empleado (hr.employee.jornal_base)
    pero puede sobreescribirse por linea (por ejemplo si se nego
    un jornal distinto para esa semana en particular).
    """
    _name = 'building.jornal.line'
    _description = 'Linea de Jornal (Trabajador/Semana)'

    # === RELACIONES ===

    jornal_id = fields.Many2one(
        'building.jornal',
        string='Jornal',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # Apunta a hr.employee (modelo nativo de Odoo, extendido con jornal_base y rol_obra_id)
    worker_id = fields.Many2one(
        'hr.employee',
        string='Trabajador',
        required=True,
        help='Seleccionar del catalogo de empleados de Odoo',
    )

    # === CAMPOS HEREDADOS DEL EMPLEADO ===

    # Rol de obra se hereda automaticamente (solo lectura)
    rol_obra_id = fields.Many2one(
        related='worker_id.rol_obra_id',
        string='Rol de Obra',
        readonly=True,
        store=True,
        help='Rol del trabajador en obra (heredado del empleado)',
    )

    # Jornal base: se copia del empleado via onchange, editable para override
    jornal_base = fields.Float(
        string='Jornal Base',
        help='Costo base por dia en MXN. Se copia del empleado '
             'pero se puede modificar para esta semana en particular.',
    )

    # === DIAS TRABAJADOS ===

    dias_trabajados = fields.Integer(
        string='Dias Trabajados',
        required=True,
        help='Dias reales que asistio el trabajador esta semana (1-7). '
             'Informativo: el costo se calcula con los dias PAGADOS del encabezado.',
    )

    # === COSTOS CALCULADOS ===

    costo_directo = fields.Float(
        string='Costo Directo',
        compute='_compute_costo_directo',
        help='dias_pagados x jornal_base (sin cargas sociales)',
    )

    costo_real = fields.Float(
        string='Costo Real',
        compute='_compute_costo_real',
        store=True,
        help='costo_directo x factor_carga_social (con IMSS, Infonavit, etc.)',
    )

    notes = fields.Char(
        string='Observaciones',
        help='Nota breve sobre esta linea (falta, medio dia, etc.)',
    )

    # === COMPUTE ===

    @api.depends('jornal_id.dias_pagados', 'jornal_base')
    def _compute_costo_directo(self):
        """
        Costo directo = dias pagados x jornal base del trabajador
        Ejemplo: 7 dias x $500/dia = $3,500
        """
        for linea in self:
            linea.costo_directo = linea.jornal_id.dias_pagados * linea.jornal_base

    @api.depends('jornal_id.dias_pagados', 'jornal_id.factor_carga_social', 'jornal_base')
    def _compute_costo_real(self):
        """
        Costo real = dias_pagados x jornal_base x factor_carga_social
        Ejemplo: 7 x $500 x 1.35 = $4,725 (incluyendo IMSS, etc.)
        """
        for linea in self:
            directo = linea.jornal_id.dias_pagados * linea.jornal_base
            linea.costo_real = directo * linea.jornal_id.factor_carga_social

    # === ONCHANGE ===

    @api.onchange('worker_id')
    def _onchange_worker_id(self):
        """Al seleccionar un empleado, copiar su jornal base como default"""
        if self.worker_id:
            self.jornal_base = self.worker_id.jornal_base

    # === CONSTRAINTS ===

    @api.constrains('dias_trabajados')
    def _check_dias_trabajados(self):
        """Validar que los dias trabajados esten entre 0 y 7"""
        for linea in self:
            if linea.dias_trabajados < 0 or linea.dias_trabajados > 7:
                raise ValidationError(
                    _("Los dias trabajados deben estar entre 0 y 7.")
                )
