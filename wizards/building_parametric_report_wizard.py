# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import xlsxwriter

class BuildingParametricReportWizard(models.TransientModel):
    _name = 'building.parametric.report.wizard'
    _description = 'Reporte Paramétrico de Obra'

    work_id = fields.Many2one('building.work', string='Obra', required=True)
    budget_id = fields.Many2one('building.budget', string='Presupuesto Base', required=True)
    
    period_type = fields.Selection([
        ('weekly', 'Semanal'),
        ('biweekly', 'Catorcenal'),
        ('monthly', 'Mensual')
    ], string='Periodo', default='biweekly', required=True)

    start_date = fields.Date(string='Fecha Inicio', required=True)
    end_date = fields.Date(string='Fecha Fin', required=True)
    
    # Campos para reporte HTML/Binario
    report_html = fields.Html(string='Reporte', readonly=True)
    excel_file = fields.Binary(string='Reporte Excel')
    excel_filename = fields.Char(string='Nombre Archivo Excel')

    def action_generate_report(self):
        """Genera el reporte en pantalla (HTML)."""
        self.ensure_one()
        # Lógica simplificada para restaurar el modelo
        html = f"""
        <div class="alert alert-info">
            Reporte Paramétrico para {self.work_id.name}<br/>
            Periodo: {self.start_date} - {self.end_date}
        </div>
        """
        self.report_html = html
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.parametric.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download_excel(self):
        """Descarga el reporte en Excel."""
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()
        worksheet.write(0, 0, "Reporte Paramétrico Restored")
        workbook.close()
        output.seek(0)
        self.excel_file = base64.b64encode(output.read())
        self.excel_filename = f"Parametrico_{self.work_id.name}.xlsx"
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.parametric.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
