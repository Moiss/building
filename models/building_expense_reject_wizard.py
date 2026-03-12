# -*- coding: utf-8 -*-
# Wizard: Rechazo de Gasto (Etapa 5.2)
# Sirve tanto para building.real.line como building.work.cost

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BuildingExpenseRejectWizard(models.TransientModel):
    """
    Wizard para rechazar un gasto real o costo operativo.
    Captura el motivo obligatorio antes de ejecutar la transicion.
    """
    _name = 'building.expense.reject.wizard'
    _description = 'Asistente de Rechazo de Gasto'

    record_id = fields.Integer(
        string='ID del Registro',
        required=True,
    )

    record_model = fields.Char(
        string='Modelo',
        required=True,
        help='Nombre del modelo a rechazar: building.real.line o building.work.cost',
    )

    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        required=True,
        help='Explica por que se rechaza para que el capturista pueda corregir.',
    )

    def action_confirm(self):
        """Ejecutar el rechazo con el motivo capturado."""
        self.ensure_one()
        if not self.rejection_reason or not self.rejection_reason.strip():
            raise UserError(_('El motivo de rechazo es obligatorio.'))
        record = self.env[self.record_model].browse(self.record_id)
        if not record.exists():
            raise UserError(_('El registro ya no existe.'))
        record._do_reject(self.rejection_reason.strip())
        return {'type': 'ir.actions.act_window_close'}
