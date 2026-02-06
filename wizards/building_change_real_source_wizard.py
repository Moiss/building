# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class BuildingChangeRealSourceWizard(models.TransientModel):
    """
    Wizard para cambiar la fuente de datos reales de una obra.
    Maneja la transición de 'Interno' a 'Contable', incluyendo:
    - Validación de dependencias (account instalado).
    - Definición de fecha de corte.
    - Opción de migración histórica de datos internos a asientos contables.
    """
    _name = 'building.change.real.source.wizard'
    _description = 'Asistente de Cambio de Fuente Real'

    work_id = fields.Many2one('building.work', string='Obra', required=True, readonly=True)
    current_source = fields.Selection(related='work_id.real_source', readonly=True)
    
    new_source = fields.Selection([
        ('internal', 'Interno (Plan A)'),
        ('accounting', 'Contabilidad (Plan B)'),
    ], string='Nueva Fuente', required=True)
    
    cutover_date = fields.Date(
        string='Fecha de Corte',
        default=fields.Date.context_today,
        help='Fecha a partir de la cual empezará a leerse la contabilidad.'
    )
    
    migration_policy = fields.Selection([
        ('cut_only', 'Solo Corte (No migrar histórico)'),
        ('migrate', 'Migrar Histórico (Generar Asientos)'),
    ], string='Política de Migración', default='cut_only',
       help='Si elige migrar, se generarán asientos contables por el total de gastos internos hasta la fecha de corte.')
       
    # Resumen de datos a migrar
    lines_to_migrate_count = fields.Integer(string='Registros a Migrar', compute='_compute_migration_stats')
    amount_to_migrate = fields.Monetary(string='Monto Total a Migrar', compute='_compute_migration_stats', currency_field='currency_id')
    currency_id = fields.Many2one(related='work_id.currency_id')
    
    # Check de compatibilidad
    account_installed = fields.Boolean(compute='_compute_account_installed')
    missing_config = fields.Text(compute='_compute_account_installed')

    @api.depends('new_source', 'cutover_date', 'work_id')
    def _compute_migration_stats(self):
        for wizard in self:
            if wizard.new_source == 'accounting' and wizard.cutover_date:
                lines = self.env['building.real.line'].search([
                    ('work_id', '=', wizard.work_id.id),
                    ('is_migrated', '=', False),
                    ('date', '<', wizard.cutover_date)
                ])
                wizard.lines_to_migrate_count = len(lines)
                wizard.amount_to_migrate = sum(lines.mapped('amount'))
            else:
                wizard.lines_to_migrate_count = 0
                wizard.amount_to_migrate = 0.0

    @api.depends('new_source')
    def _compute_account_installed(self):
        module_account = self.env['ir.module.module'].search([('name', '=', 'account'), ('state', '=', 'installed')], limit=1)
        installed = bool(module_account)
        ICPSudo = self.env['ir.config_parameter'].sudo()
        journal_id = ICPSudo.get_param('building.migration_journal_id')
        debit_acc = ICPSudo.get_param('building.migration_debit_account_id')
        credit_acc = ICPSudo.get_param('building.migration_credit_account_id')
        
        for wizard in self:
            wizard.account_installed = installed
            if not installed:
                wizard.missing_config = _("El módulo de Contabilidad ('account') no está instalado.")
            elif not (journal_id and debit_acc and credit_acc):
                 wizard.missing_config = _("Falta configurar las cuentas de migración en Ajustes.")
            else:
                 wizard.missing_config = False

    def action_confirm_change(self):
        self.ensure_one()
        work = self.work_id
        
        if self.new_source == 'internal':
            # Vuelta a Internal es trivial, solo cambiar flag.
            # OJO: Validar si quiere borrar fecha de corte?
            work.write({
                'real_source': 'internal',
                'real_cutover_date': False
            })
            return {'type': 'ir.actions.act_window_close'}
            
        # Cambio a Accounting
        if self.new_source == 'accounting':
            if not self.cutover_date:
                raise UserError(_('Debe definir una fecha de corte.'))
                
            # Validar política
            if self.migration_policy == 'migrate':
                if not self.account_installed or self.missing_config:
                     raise UserError(_('No se puede migrar: %s') % self.missing_config)
                
                # Ejecutar migración
                self._execute_migration()
            
            # Aplicar cambios en Obra
            work.write({
                'real_source': 'accounting',
                'real_cutover_date': self.cutover_date
            })
            
        return {'type': 'ir.actions.act_window_close'}

    def _execute_migration(self):
        """
        Genera asiento contable y marca líneas.
        """
        ICPSudo = self.env['ir.config_parameter'].sudo()
        journal_id = int(ICPSudo.get_param('building.migration_journal_id'))
        debit_acc_id = int(ICPSudo.get_param('building.migration_debit_account_id'))
        credit_acc_id = int(ICPSudo.get_param('building.migration_credit_account_id'))
        
        lines_to_migrate = self.env['building.real.line'].search([
            ('work_id', '=', self.work_id.id),
            ('is_migrated', '=', False),
            ('date', '<', self.cutover_date)
        ])
        
        if not lines_to_migrate:
            return

        # Agrupar por Partida para reducir líneas de asiento
        grouped_amounts = {} # {budget_line: amount}
        for line in lines_to_migrate:
            if line.budget_line_id not in grouped_amounts:
                grouped_amounts[line.budget_line_id] = 0.0
            grouped_amounts[line.budget_line_id] += line.amount
            
        # Crear asiento
        move_vals = {
            'journal_id': journal_id,
            'date': self.cutover_date,
            'ref': f"MIGRACION OBRA {self.work_id.name}",
            'line_ids': [],
        }
        
        total_migrated = 0.0
        
        for budget_line, amount in grouped_amounts.items():
            if amount <= 0: continue
            
            # Linea de Gasto (Debit)
            move_vals['line_ids'].append((0, 0, {
                'account_id': debit_acc_id,
                'name': f"Migración {budget_line.name}",
                'debit': amount,
                'credit': 0.0,
                # TODO: Analytics integration if needed
            }))
             # Linea Puente (Credit) - Sumarizada o por linea?
             # Mejor una contrapartida por linea para claridad o una total?
             # Una total es más limpio para la cuenta puente.
            total_migrated += amount

        move_vals['line_ids'].append((0, 0, {
            'account_id': credit_acc_id,
            'name': f"Contrapartida Migración {self.work_id.name}",
            'debit': 0.0,
            'credit': total_migrated,
        }))

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        # Marcar líneas internas
        lines_to_migrate.write({
            'is_migrated': True,
            'migrated_move_id': move.id,
            'migrated_on': fields.Datetime.now(),
            'migrated_by': self.env.user.id
        })
