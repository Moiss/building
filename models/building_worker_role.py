# -*- coding: utf-8 -*-
# Modelo: building.worker.role
# Catalogo de roles de obra (Fase 4.5 - Jornales)

from odoo import models, fields


class BuildingWorkerRole(models.Model):
    """
    Catalogo configurable de roles de obra.

    Permite agregar nuevos roles sin modificar codigo.
    Los roles iniciales (Oficial, Albanil, Peon, etc.) se cargan
    automaticamente via data XML al instalar el modulo.

    Se usa en hr.employee (campo rol_obra_id) para clasificar
    a los trabajadores segun su oficio en obra.
    """
    _name = 'building.worker.role'
    _description = 'Rol de Obra'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Rol',
        required=True,
        help='Nombre del oficio o especialidad (ej: Oficial, Albanil, Peon)',
    )

    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Desmarcar para archivar el rol sin eliminarlo',
    )
