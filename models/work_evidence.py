# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class BuildingWorkEvidence(models.Model):
    """
    Modelo documental para registrar evidencias fotográficas y archivos PDF
    de la obra. Clasifica las evidencias por tipo (avance, entrega, incidencia)
    y las vincula a la obra, etapa y opcionalmente partida.
    
    Preparado para integración futura con app móvil (Flutter) mediante campos
    de geolocalización y dispositivo.
    """
    _name = 'building.work.evidence'
    _description = 'Evidencia de Obra'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Campos Principales ---
    name = fields.Char(
        string='Descripción',
        required=True,
        tracking=True
    )

    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa / Frente',
        required=True,
        index=True,
        tracking=True,
        domain="[('work_id', '=', work_id)]"
    )

    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida',
        required=False,
        domain="[('work_id', '=', work_id)]",
        help="Opcional: vincule a una partida del presupuesto"
    )

    evidence_type = fields.Selection(
        [
            ('progress', 'Avance Físico'),
            ('delivery', 'Entrega de Material'),
            ('issue', 'Problema / Incidencia'),
        ],
        string='Tipo de Evidencia',
        required=True,
        default='progress',
        tracking=True
    )

    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
        index=True
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'evidence_attachment_rel',
        'evidence_id',
        'attachment_id',
        string='Documentos Generales',
        help='Archivos PDF, facturas o documentos técnicos'
    )

    attachment_before_ids = fields.Many2many(
        'ir.attachment',
        'evidence_before_rel',
        'evidence_id',
        'attachment_id',
        string='Fotos Antes',
        help='Evidencia fotográfica previa'
    )

    attachment_after_ids = fields.Many2many(
        'ir.attachment',
        'evidence_after_rel',
        'evidence_id',
        'attachment_id',
        string='Fotos Después',
        help='Evidencia fotográfica posterior'
    )

    notes = fields.Text(
        string='Notas'
    )

    # --- Campos Preparados para Flutter (Futuro) ---
    gps_latitude = fields.Float(
        string='Latitud GPS',
        digits=(10, 7),
        help="Se llenará automáticamente desde la app móvil"
    )

    gps_longitude = fields.Float(
        string='Longitud GPS',
        digits=(10, 7)
    )

    captured_at = fields.Datetime(
        string='Capturado en',
        help="Timestamp de cuando se tomó la foto en campo"
    )

    captured_by = fields.Many2one(
        'res.users',
        string='Capturado por',
        default=lambda self: self.env.user
    )

    device_id = fields.Char(
        string='ID Dispositivo',
        help="ID del dispositivo móvil (futuro Flutter)"
    )

    # --- Campos Computados ---
    attachment_count = fields.Integer(
        string='Archivos',
        compute='_compute_attachment_count',
        store=False
    )
    
    # Related para facilitar vistas y dominios
    currency_id = fields.Many2one(
        related='work_id.currency_id',
        string='Moneda'
    )
    company_id = fields.Many2one(
        related='work_id.company_id',
        string='Compañía',
        store=True
    )

    @api.depends('attachment_ids', 'attachment_before_ids', 'attachment_after_ids')
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = (
                len(record.attachment_ids) + 
                len(record.attachment_before_ids) + 
                len(record.attachment_after_ids)
            )

    @api.onchange('work_id')
    def _onchange_work_id(self):
        """Si cambia la obra, limpiar los campos dependientes para evitar inconsistencias."""
        if self.work_id:
            self.stage_id = False
            self.budget_line_id = False

    @api.onchange('budget_line_id')
    def _onchange_budget_line_id(self):
        """Al seleccionar partida, sugerir su nombre como descripción."""
        if self.budget_line_id:
            self.name = self.budget_line_id.name

    @api.constrains('work_id', 'stage_id', 'budget_line_id')
    def _check_scope_integrity(self):
        """Verifica que la etapa y la partida pertenezcan a la obra seleccionada."""
        for record in self:
            if record.work_id and record.stage_id:
                if record.stage_id.work_id != record.work_id:
                    raise ValidationError(_("La etapa seleccionada no pertenece a esta obra."))
            
            if record.work_id and record.budget_line_id:
                if record.budget_line_id.work_id != record.work_id:
                    raise ValidationError(_("La partida seleccionada no pertenece a esta obra."))
