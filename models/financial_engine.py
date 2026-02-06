# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class BuildingFinancialEngine(models.AbstractModel):
    """
    Motor Financiero Centralizado.
    Calcula gastos reales comparando fuentes (interna vs contable)
    y métricas de variación.
    """
    _name = 'building.financial.engine'
    _description = 'Motor Financiero'

    @api.model
    def get_real_amounts(self, work_id, stage_ids=None, line_ids=None):
        """
        Retorna diccionario con montos reales agrupados por ID.
        Depende de work.real_source.
        """
        work = self.env['building.work'].browse(work_id)
        if not work:
            return {}

        amounts = {} # {line_id: amount} or {stage_id: amount} logic to be defined by caller need
        
        # En esta implementación simplificada, retornamos totales por objeto solicitado.
        # Pero para eficiencia, calculamos todo lo necesario.
        
        # Estrategia: Calcular por PARTIDA (granularidad más baja) y luego sumarizar.
        
        domain = [('work_id', '=', work.id)]
        if line_ids:
            domain.append(('budget_line_id', 'in', line_ids))
            
        RealLine = self.env['building.real.line']
        
        # 1. FUENTE INTERNA (Plan A)
        # Sumar todas las no migradas.
        # Si fuente es Accounting, sumar solo las pre-corte (que conceptualmente son historicas no migradas o migradas)
        # NOTA: Si hubo migración, las lineas tienen is_migrated=True.
        # El motor debe decidir: ¿Sumamos is_migrated?
        # NO. Si is_migrated=True, se asume que YA están en contabilidad (account.move).
        # Por tanto, si leemos de contabilidad, ya vendrán ahí.
        
        # Si real_source = 'internal':
        #   Sumar TODAS las internas activo (no borradas). (is_migrated debería ser False siempre, salvo glitch)
        
        # Si real_source = 'accounting':
        #   A) Sumar Contabilidad (account.move.line)
        #   B) Sumar Internas que NO han sido migradas y fecha < corte (caso "Solo Corte").
        
        internal_domain = domain + []
        
        if work.real_source == 'internal':
             # Plan A puro: Todo lo interno vale
             pass
        else:
             # Plan B: Contabilidad Activada
             # Excluir las migradas (porque se sumaran via asientos)
             internal_domain.append(('is_migrated', '=', False))
             
             # Adicionalmente, si hay fecha de corte, asegurar que no sumamos cosas futuras por error
             if work.real_cutover_date:
                 internal_domain.append(('date', '<', work.real_cutover_date))

        # Agrupar por budget_line_id
        # read_group es lo más eficiente
        groups = RealLine.read_group(internal_domain, ['budget_line_id', 'amount'], ['budget_line_id'])
        
        real_amounts_by_line = {g['budget_line_id'][0]: g['amount'] for g in groups}
        
        # 2. FUENTE CONTABLE (Plan B)
        if work.real_source == 'accounting':
            # TODO: Implementar query a account.move.line
            # Por ahora retorna 0 + lo interno válido (Solo Corte)
            pass
            
        return real_amounts_by_line

    @api.model
    def get_stage_financial_totals(self, work_id, stage_ids=None):
        """
        Retorna totales financieros agrupados por etapa (budget y real).
        Estructura: {stage_id: {'budget': float, 'real': float}}
        """
        work = self.env['building.work'].browse(work_id)
        if not work:
            return {}

        domain_stages = [('work_id', '=', work.id)]
        if stage_ids:
            domain_stages.append(('id', 'in', stage_ids))

        stages = self.env['building.work.stage'].search(domain_stages)
        
        # 1. Calcular Presupuesto por Etapa (Suma de partidas)
        # Eficiente: read_group sobre building.budget.line
        BudgetLine = self.env['building.budget.line']
        budget_groups = BudgetLine.read_group(
            [('work_id', '=', work_id), ('stage_id', 'in', stages.ids)],
            ['stage_id', 'amount'],
            ['stage_id']
        )
        budget_map = {g['stage_id'][0]: g['amount'] for g in budget_groups}

        # 2. Calcular Real por Etapa (Delegar a get_real_amounts)
        # Obtenemos real por partida y sumamos, O implementar get_real_amounts por stage
        # Para eficiencia, hagámoslo directo aquí similar a get_real_amounts pero agrupando por stage
        
        RealLine = self.env['building.real.line']
        real_domain = [('work_id', '=', work.id), ('stage_id', 'in', stages.ids)]
        
        # Lógica de fuente (copiada de get_real_amounts simplificada)
        if work.real_source == 'accounting':
             real_domain.append(('is_migrated', '=', False))
             if work.real_cutover_date:
                 real_domain.append(('date', '<', work.real_cutover_date))
        
        real_groups = RealLine.read_group(
            real_domain,
            ['stage_id', 'amount'],
            ['stage_id']
        )
        real_map = {g['stage_id'][0]: g['amount'] for g in real_groups}

        # 3. Construir resultado
        result = {}
        for stage in stages:
            result[stage.id] = {
                'budget': budget_map.get(stage.id, 0.0),
                'real': real_map.get(stage.id, 0.0)
            }
        return result

    @api.model
    def calculate_variance(self, budget, real):
        try:
            return real - budget
        except:
            return 0.0

    @api.model
    def get_traffic_light(self, budget, real, threshold_warning=90.0, threshold_critical=100.0):
        """
        Calcula semáforo según umbrales (por defecto 90/100).
        Verde: % <= 90
        Amarillo: 90 < % <= 100
        Rojo: % > 100
        """
        if budget <= 0:
            if real > 0:
                # Caso borde: Sin presupuesto pero con gasto -> Rojo
                # (Podría ser configurable, pero por defecto es alerta máxima)
                return 'red'
            return 'green' # 0 presupuesto, 0 gasto -> Verde
            
        pct = (real / budget) * 100.0
        
        # Lógica estricta según requerimiento 3.3.1
        if pct > threshold_critical:
            return 'red'
        elif pct > threshold_warning:
            return 'yellow'
        return 'green'
