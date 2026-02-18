# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api

def migrate(cr, version):
    """Elimina columnas obsoletas del tab Presupuesto vs Real."""
    cr.execute("ALTER TABLE building_work DROP COLUMN IF EXISTS real_source;")
    cr.execute("ALTER TABLE building_work DROP COLUMN IF EXISTS real_cutover_date;")
