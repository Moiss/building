# -*- coding: utf-8 -*-
"""
Modelo: Alertas de Obra (building.work.alert)
Sistema de alertas para desviaciones, aprobaciones y notificaciones.
"""

from odoo import models, fields, api


class BuildingWorkAlert(models.Model):
    """
    Alerta de Obra.
    Notificaciones sobre desviaciones, aprobaciones pendientes, etc.
    """
    _name = 'building.work.alert'
    _description = 'Alerta de Obra'
    _order = 'severity desc, create_date desc'

    # === CAMPOS PRINCIPALES ===
    name = fields.Char(
        string='Descripción',
        required=True,
        help='Descripción de la alerta'
    )
    
    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    severity = fields.Selection([
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('critical', 'Crítico'),
    ], string='Severidad', required=True, default='info')
    
    alert_type = fields.Selection([
        ('approval', 'Aprobación Pendiente'),
        ('budget', 'Desviación Presupuesto'),
        ('deviation', 'Desviación General'),
        ('invoice', 'Factura Pendiente'),
        ('financial', 'Financiera'),
        ('time', 'Retraso de Etapa'),
        ('consistency', 'Inconsistencia Avance'),
        ('planning', 'Planeación'),
        ('operational', 'Operativa'),
        ('liquidity', 'Liquidez'),
        ('other', 'Otro'),
    ], string='Tipo', required=True, default='other')
    
    rule_code = fields.Char(
        string='Código de Regla',
        index=True,
        help='Identificador único de la regla que generó esta alerta (para evitar duplicados)'
    )
    
    is_active = fields.Boolean(
        string='Activa',
        default=True,
        help='Las alertas inactivas no se muestran en el dashboard'
    )
    
    # === CAMPOS DE NAVEGACIÓN (opcional MVP) ===
    action_xml_id = fields.Char(
        string='XML ID de Acción',
        help='XML ID de la acción a ejecutar al hacer clic'
    )
    
    action_res_id = fields.Integer(
        string='ID de Recurso',
        help='ID del registro relacionado'
    )
    
    # === CAMPOS RELACIONADOS ===
    company_id = fields.Many2one(
        related='work_id.company_id',
        store=True,
        readonly=True
    )
    
    # === CAMPOS COMPUTADOS PARA UI ===
    severity_icon = fields.Char(
        string='Ícono',
        compute='_compute_severity_icon'
    )

    alert_emoji = fields.Char(
        string='Emoji',
        compute='_compute_alert_emoji',
        help='Emoji visual según severidad'
    )

    @api.depends('severity')
    def _compute_severity_icon(self):
        """Retorna el ícono FontAwesome según la severidad."""
        icons = {
            'info': 'fa-info-circle',
            'warning': 'fa-exclamation-triangle',
            'critical': 'fa-times-circle',
        }
        for alert in self:
            alert.severity_icon = icons.get(alert.severity, 'fa-bell')

    @api.depends('severity')
    def _compute_alert_emoji(self):
        """Retorna emoji según severidad."""
        emojis = {
            'critical': '🔴',
            'warning': '🟡',
            'info': '🔵',
        }
        for alert in self:
            alert.alert_emoji = emojis.get(alert.severity, '⚪')

    def action_dismiss(self):
        """Desactiva/oculta la alerta."""
        self.write({'is_active': False})

    def action_navigate(self):
        """
        Navega al recurso relacionado con la alerta.
        Requiere action_xml_id y opcionalmente action_res_id.
        """
        self.ensure_one()
        if not self.action_xml_id:
            return False
        
        action = self.env['ir.actions.act_window']._for_xml_id(self.action_xml_id)
        if self.action_res_id:
            action['res_id'] = self.action_res_id
            action['view_mode'] = 'form'
        return action
