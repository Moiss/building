# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class BuildingWorkCost(models.Model):
    """
    Modelo de Costos Operativos de Obra (Etapa 4.1).
    Permite registrar gastos presupuestados (ligados a partida) y adicionales (indirectos).
    NO afecta avance físico.
    """
    _name = 'building.work.cost'
    _description = 'Costo Operativo de Obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Descripción Corta',
        required=True,
        tracking=True,
        help='Referencia o concepto breve del costo'
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
        string='Etapa',
        domain="[('work_id', '=', work_id)]",
        index=True,
        tracking=True,
        help='Etapa opcional para clasificación'
    )

    cost_type = fields.Selection([
        ('budgeted', 'Presupuestado'),
        ('additional', 'Adicional / Indirecto')
    ], string='Tipo de Costo', required=True, default='additional', tracking=True)

    budget_line_id = fields.Many2one(
        'building.budget.line',
        string='Partida Presupuestaria',
        domain="[('work_id', '=', work_id)]",
        index=True,
        tracking=True,
        help='Opcional: vincule a una partida del presupuesto si este gasto corresponde a alguna'
    )

    date = fields.Date(
        string='Fecha',
        default=fields.Date.context_today,
        required=True,
        index=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        help='Producto o servicio del gasto'
    )

    description = fields.Text(string='Descripción Detallada')

    qty = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida'
    )

    unit_cost = fields.Monetary(
        string='Costo Unitario',
        currency_field='currency_id',
        default=0.0,
        required=True
    )

    amount = fields.Monetary(
        string='Monto Total',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='work_id.currency_id',
        store=True,
        readonly=True
    )

    company_id = fields.Many2one(
        'res.company',
        related='work_id.company_id',
        store=True,
        readonly=True
    )
    
    active = fields.Boolean(default=True)

    # === FLUJO DE APROBACIÓN (ETAPA 5.2) ===

    approval_state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('submitted', 'En Revisión'),
            ('approved', 'Aprobado'),
            ('rejected', 'Rechazado'),
        ],
        string='Estado Aprobación',
        default='draft',
        required=True,
        tracking=True,
        help='Flujo: Borrador → En Revisión → Aprobado / Rechazado',
    )

    approval_date = fields.Datetime(
        string='Fecha Aprobación',
        readonly=True,
        copy=False,
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Aprobado Por',
        readonly=True,
        copy=False,
    )

    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        copy=False,
    )

    # === COMPUTE ===
    @api.depends('qty', 'unit_cost')
    def _compute_amount(self):
        for record in self:
            record.amount = record.qty * record.unit_cost

    # === ONCHANGE ===
    @api.onchange('work_id')
    def _onchange_work_id(self):
        if self.stage_id and self.stage_id.work_id != self.work_id:
            self.stage_id = False
        if self.budget_line_id and self.budget_line_id.work_id != self.work_id:
            self.budget_line_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.uom_id:
                self.uom_id = self.product_id.uom_id
            if not self.name:
                self.name = self.product_id.name
            # Sugerir costo estándar si no hay uno
            if self.unit_cost == 0.0:
                self.unit_cost = self.product_id.standard_price

    # === CONSTRAINTS ===
    @api.constrains('work_id', 'stage_id', 'budget_line_id')
    def _check_scope_integrity(self):
        for record in self:
            if record.stage_id and record.stage_id.work_id != record.work_id:
                raise ValidationError(_("La etapa seleccionada no pertenece a la obra."))
            if record.budget_line_id and record.budget_line_id.work_id != record.work_id:
                raise ValidationError(_("La partida seleccionada no pertenece a la obra."))

    # === EVIDENCIAS (ETAPA 4.2) ===
    evidence_ids = fields.One2many(
        'building.work.evidence',
        'cost_id',
        string='Evidencias'
    )
    
    evidence_count = fields.Integer(
        string='# Evidencias',
        compute='_compute_evidence_count',
        store=False
    )
    
    def _compute_evidence_count(self):
        """Cuenta las evidencias relacionadas con este costo."""
        for record in self:
            record.evidence_count = len(record.evidence_ids)

    def action_view_evidences(self):
        """Ver evidencias asociadas al costo."""
        self.ensure_one()
        return {
            'name': _('Evidencias'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.work.evidence',
            'view_mode': 'list,form',
            'domain': [('cost_id', '=', self.id)],
            'context': {
                'default_work_id': self.work_id.id,
                'default_stage_id': self.stage_id.id,
                'default_cost_id': self.id
            },
        }

    # === CRUD OVERRIDES (TRIGGER ENGINE) ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['cost_type'] = 'additional'
        records = super().create(vals_list)
        records.mapped('work_id')._recompute_cost_totals()
        return records

    def write(self, vals):
        # Optimización: solo recomponer si cambian campos relevantes
        recompute = any(f in vals for f in [
            'amount', 'qty', 'unit_cost', 'cost_type', 'work_id', 'active', 'approval_state'
        ])
        res = super().write(vals)
        if recompute:
            self.mapped('work_id')._recompute_cost_totals()
        return res

    def unlink(self):
        works = self.mapped('work_id')
        res = super().unlink()
        works._recompute_cost_totals()
        return res

    # === FLUJO DE APROBACIÓN (ETAPA 5.2) ===

    def _check_approval_rights(self):
        """Solo Director o Administrador de Obra pueden aprobar / rechazar."""
        if not (
            self.env.user.has_group('building_dashboard.group_building_director') or
            self.env.user.has_group('building_dashboard.group_building_manager')
        ):
            raise UserError(_(
                'Solo el Director o el Administrador de Obra puede aprobar o rechazar gastos.'
            ))

    def action_submit(self):
        """Enviar a revisión: draft → submitted"""
        for rec in self:
            if rec.approval_state != 'draft':
                raise UserError(_('Solo se pueden enviar gastos en estado Borrador.'))
        self.write({'approval_state': 'submitted'})
        for rec in self:
            rec.message_post(body=_('Gasto enviado a revisión por %s.') % self.env.user.name)

    def action_approve(self):
        """Aprobar: submitted → approved"""
        self._check_approval_rights()
        for rec in self:
            if rec.approval_state != 'submitted':
                raise UserError(_('Solo se pueden aprobar gastos En Revisión.'))
        self.write({
            'approval_state': 'approved',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.uid,
        })
        for rec in self:
            rec.message_post(body=_('Gasto aprobado por %s.') % self.env.user.name)

    def action_open_reject_wizard(self):
        """Abrir wizard de rechazo para capturar el motivo."""
        self.ensure_one()
        self._check_approval_rights()
        if self.approval_state != 'submitted':
            raise UserError(_('Solo se pueden rechazar gastos En Revisión.'))
        wizard = self.env['building.expense.reject.wizard'].create({
            'record_id': self.id,
            'record_model': self._name,
        })
        return {
            'name': _('Rechazar Gasto'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.expense.reject.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _do_reject(self, reason):
        """Ejecutar rechazo con motivo (llamado desde wizard)."""
        for rec in self:
            if rec.approval_state != 'submitted':
                raise UserError(_('Solo se pueden rechazar gastos En Revisión.'))
        self.write({
            'approval_state': 'rejected',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.uid,
            'rejection_reason': reason,
        })
        for rec in self:
            rec.message_post(
                body=_('Gasto rechazado por %s. Motivo: %s') % (self.env.user.name, reason)
            )

    def action_reset_draft(self):
        """Regresar a borrador: rejected → draft"""
        for rec in self:
            if rec.approval_state != 'rejected':
                raise UserError(_('Solo se pueden regresar a borrador gastos Rechazados.'))
        self.write({
            'approval_state': 'draft',
            'rejection_reason': False,
            'approved_by': False,
            'approval_date': False,
        })
        for rec in self:
            rec.message_post(
                body=_('Gasto regresado a Borrador por %s para corrección.') % self.env.user.name
            )