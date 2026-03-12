# -*- coding: utf-8 -*-
# Herencia: hr.employee
# Extiende el empleado nativo de Odoo con campos de obra (Fase 4.5 - Jornales)

from odoo import models, fields


class HrEmployeeBuilding(models.Model):
    """
    Extension de hr.employee para Control de Obras.

    Agrega dos campos al empleado nativo:
    - jornal_base: costo por dia de trabajo en pesos MXN
    - rol_obra_id: rol/oficio en obra (del catalogo building.worker.role)

    Esto permite reutilizar toda la infraestructura nativa de Odoo
    (asistencia, nomina, CURP, IMSS) sin reconstruirla desde cero.
    """
    _inherit = 'hr.employee'

    jornal_base = fields.Float(
        string='Jornal Base (MXN/dia)',
        default=0.0,
        help='Costo por dia de trabajo en pesos mexicanos. '
             'Se usa como default en las lineas de jornal semanal.',
    )

    rol_obra_id = fields.Many2one(
        'building.worker.role',
        string='Rol de Obra',
        help='Oficio o especialidad del trabajador en obra '
             '(Oficial, Albanil, Peon, etc.)',
    )
