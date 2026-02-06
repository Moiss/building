# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BuildingChapterLoaderWizard(models.TransientModel):
    _name = 'building.chapter.loader.wizard'
    _description = 'Wizard: Cargar Partidas desde Capítulo'

    stage_id = fields.Many2one(
        'building.work.stage',
        string='Etapa Destino',
        required=True,
        readonly=True
    )
    
    work_id = fields.Many2one(
        related='stage_id.work_id',
        readonly=True
    )

    budget_id = fields.Many2one(
        'building.budget',
        string='Presupuesto',
        domain="[('work_id', '=', work_id)]",
        required=True 
    )

    chapter_ids = fields.Many2many(
        'building.budget.chapter',
        string='Capítulos a Cargar',
        domain="[('budget_id', '=', budget_id)]"
    )

    mode = fields.Selection([
        ('skip', 'Omitir Duplicados (Append)'),
        ('replace', 'Reemplazar (Borrar existentes en Etapa)'),
        ('sync', 'Sincronizar Importes (Actualizar existentes)'),
    ], string='Modo de Carga (Deprecated)', default='skip') # Deprecated but kept for DB compatibility if needed usually removd

    reassign_mode = fields.Selection([
        ('no_reassign', 'Solo Asignar Partidas Libres'),
        ('reassign', 'Reasignar Partidas (Mover de otra etapa)'),
    ], string='Modo de Asignación', default='no_reassign', required=True,
       help="Defina qué hacer con partidas que ya tienen etapa asignada.")

    @api.onchange('work_id')
    def _onchange_work_id(self):
        """Pre-selecciona el presupuesto activo de la obra si existe."""
        if self.work_id:
            # Buscar presupuesto validado o el más reciente
            # Preferir 'validated' > 'draft'
            budgets = self.env['building.budget'].search([
                ('work_id', '=', self.work_id.id)
            ], order='state desc, id desc')
            if budgets:
                self.budget_id = budgets[0]

    def action_load_lines(self):
        self.ensure_one()
        if not self.chapter_ids:
            raise UserError(_("Por favor seleccione al menos un capítulo."))

        Stats = {'assigned': 0, 'moved': 0, 'skipped': 0}
        
        # Contexto para permitir asignación incluso en presupuesto validado
        ctx = dict(self.env.context)
        ctx['allow_stage_assignment_on_validated'] = True
        
        # Iterar Capítulos y sus Partidas
        # Ya no buscamos "existentes" para clonar. Trabajamos directamente sobre las partidas del presupuesto.
        for chapter in self.chapter_ids:
            for line in chapter.line_ids:
                
                # 0. Canonical Check (Detectar duplicados históricos)
                # Protegemos el wizard de actuar sobre datos sucios.
                domain = [
                    ('budget_id', '=', self.budget_id.id),
                    ('chapter_id', '=', chapter.id),
                    ('code', '=', line.code)
                ]
                if self.env['building.budget.line'].search_count(domain) > 1:
                     raise UserError(_(
                         'Error Crítico de Integridad: Se detectaron duplicados para la partida "%s".\n'
                         'El sistema no puede continuar automáticante.\n'
                         'Solicite a un Administrador Técnico limpiar la base de datos.'
                     ) % line.display_name)

                # Caso 1: Ya está en la etapa destino
                if line.stage_id == self.stage_id:
                    Stats['skipped'] += 1
                    continue
                
                # Caso 2: Tiene etapa asignada (pero distinta)
                if line.stage_id:
                    if self.reassign_mode == 'reassign':
                        # MOVER
                        line.with_context(ctx).write({'stage_id': self.stage_id.id})
                        Stats['moved'] += 1
                    else:
                        # OMITIR (Está ocupada)
                        Stats['skipped'] += 1
                
                # Caso 3: No tiene etapa (Libre)
                else:
                    # ASIGNAR
                    line.with_context(ctx).write({'stage_id': self.stage_id.id})
                    Stats['assigned'] += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asignación Completa'),
                'message': _('Procesado. Asignadas: %s, Movidas: %s, Omitidas: %s') % (Stats['assigned'], Stats['moved'], Stats['skipped']),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}, 
            }
        }
