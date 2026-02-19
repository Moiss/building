# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import json

_logger = logging.getLogger(__name__)

class BuildingAIChat(models.Model):
    _name = 'building.ai.chat'
    _description = 'Chat IA para Generación de Obras'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Título', default='Nuevo Chat', required=True)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, required=True)
    
    message_ids = fields.One2many(
        'building.ai.chat.message', 
        'chat_id', 
        string='Historial de Conversación'
    )
    
    last_prompt = fields.Text(string='Último Prompt')
    last_response = fields.Text(string='Última Respuesta')
    has_generated_work = fields.Boolean(string='Obra Generada', default=False)
    generated_work_id = fields.Many2one('building.work', string='Obra Generada') # Campo para linkear
    
    def action_send_message(self):
        """Envía el mensaje al servicio de IA configurado."""
        self.ensure_one()
        if not self.last_prompt:
            raise UserError(_('Por favor escriba un mensaje antes de enviar.'))

        # 1. Guardar mensaje de usuario
        self.env['building.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'user',
            'content': self.last_prompt,
        })
        
        # 2. Preparar contexto
        # Obtener historial reciente para contexto
        history = []
        for msg in self.message_ids.sorted('create_date'):
            history.append({
                'role': msg.role, 
                'content': msg.content
            })
            
        system_prompt = self._get_system_prompt()
        
        # 3. Llamar al servicio
        service = self.env['building.ai.service']
        try:
            # work_id=False porque estamos generando una NUEVA obra, no editando una existente
            ai_response_content = service.send_message(history, system_prompt, work_id=False)
            
            # 4. Guardar respuesta de IA
            self.env['building.ai.chat.message'].create({
                'chat_id': self.id,
                'role': 'assistant',
                'content': ai_response_content,
                'has_generation': ('```json' in ai_response_content)
            })
            
            self.last_response = ai_response_content
            self.last_prompt = False # Limpiar input
            
            # 5. Intentar procesar JSON si existe
            if '```json' in ai_response_content:
                work = self._process_ai_json(ai_response_content)
                if work:
                    self.generated_work_id = work.id
                    self.has_generated_work = True
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Obra Generada'),
                            'message': _('Se ha creado la obra "%s" correctamente.') % work.name,
                            'type': 'success',
                            'sticky': False,
                        }
                    }

        except Exception as e:
            _logger.error("Error en Chat IA: %s", str(e))
            raise UserError(_('Error al comunicarse con la IA: %s') % str(e))
            
        return self._reload_form()

    def _get_system_prompt(self):
        """Retorna el prompt de sistema actualizado con nuevos campos."""
        return """ERES UN EXPERTO ARQUITECTO Y GERENTE DE OBRA DE MÉXICO.
Tu objetivo es ayudar al usuario a planificar obras de construcción, generando presupuestos detallados.

TASAS Y PRECIOS:
- Usa precios realistas de mercado para México en 2026 (MXN).
- Considera mano de obra, materiales y equipo.

FORMATO DE RESPUESTA:
Si el usuario te pide generar una obra o presupuesto, DEBES responder con un bloque de código JSON estrictamente formateado así:

```json
{
  "name": "Nombre del Proyecto",
  "description": "Descripción breve del alcance",
  "total_budget": 150000.00,
  "duration_months": 3,
  "etapas": [
    {
      "name": "Cimentación",
      "description": "Excavación y colado de zapatas",
      "sequence": 10,
      "weight": 20.0,
      "state": "planning"
    },
    {
      "name": "Estructura",
      "description": "Levantamiento de muros y castillos",
      "sequence": 20,
      "weight": 50.0,
      "state": "planning"
    }
  ],
  "partidas": [
    {
      "code": "CIM-01",
      "name": "Limpieza y trazo",
      "unit": "m2",
      "quantity": 100.0,
      "unit_price": 50.0,
      "amount": 5000.00,
      "period_from": 1,
      "period_to": 1,
      "etapa_idx": 0
    },
    {
      "code": "EST-01",
      "name": "Muro de Block",
      "unit": "m2",
      "quantity": 200.0,
      "unit_price": 450.0,
      "amount": 90000.00,
      "period_from": 2,
      "period_to": 3,
      "etapa_idx": 1
    }
  ]
}
```

REGLAS IMPORTANTES:
1. "etapas" define la estructura macro. Incluye `weight` (peso porcentual, suma 100) y `description`.
2. "partidas" son los conceptos unitarios. DEBEN incluir:
   - `unit`: Unidad de medida (m2, ml, pza, lote, kg, ton).
   - `quantity`: Cantidad estimada.
   - `unit_price`: Precio unitario.
   - `amount`: Resultado de quantity * unit_price.
   - `etapa_idx`: Índice (0-based) de la etapa en el array "etapas" a la que pertenece.
   - `period_from`, `period_to`: Mes inicio/fin (enteros 1..N).

SIEMPRE responde en español profesional.
"""

    def _process_ai_json(self, response_text):
        """Extrae y procesa el JSON de la respuesta."""
        try:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            json_str = response_text[start:end].strip()
            data = json.loads(json_str)
            return self._create_work_from_json(data)
        except Exception as e:
            _logger.error("Error parsing JSON: %s", str(e))
            return False

    def _find_or_create_uom(self, uom_name):
        """Busca una UdM por nombre (insensible a mayúsculas) o la crea."""
        if not uom_name:
            return False
            
        # Normalizar
        name = uom_name.strip()
        
        # Buscar existente
        Uom = self.env['uom.uom']
        # Buscar primero insensitive
        existing = Uom.search([('name', '=ilike', name)], limit=1)
        if existing:
            return existing
            
        # Buscar por categoría 'Unit' o crear
        # Asumimos categoría por defecto "Unit" (ID 1 usualmente) o buscamos una
        # Odoo standard: Module 'uom'
        category = self.env.ref('uom.product_uom_categ_unit', raise_if_not_found=False)
        if not category:
            category = self.env['uom.category'].search([], limit=1)
            
        try:
            return Uom.create({
                'name': name,
                'category_id': category.id if category else False,
                'uom_type': 'smaller', # Para no ser referencia y evitar problemas
                'ratio': 1.0, 
                'active': True
            })
        except:
            # Fallback si falla creación por permisos u otro
            return False

    def _create_work_from_json(self, data):
        """Crea la obra y presupuesto a partir de los datos JSON."""
        # 1. Crear Obra
        work_vals = {
            'name': data.get('name', 'Obra Generada por IA'),
            'description': data.get('description'),
            'date_start': fields.Date.context_today(self),
            # total_budget es computado, pero podemos ponerlo en description
        }
        work = self.env['building.work'].create(work_vals)
        
        # 2. Crear Presupuesto Base
        budget = self.env['building.budget'].create({
            'work_id': work.id,
            'name': 'Presupuesto Base (IA)',
            'date_start': fields.Date.context_today(self),
            'duration_months': int(data.get('duration_months', 6)),
            'description': f"Generado por IA. Presupuesto estimado: ${data.get('total_budget', 0)}"
        })
        
        # 3. Crear Etapas
        etapas_map = {} # index -> stage_id
        for idx, etapa_data in enumerate(data.get('etapas', [])):
            stage = self.env['building.work.stage'].create({
                'work_id': work.id,
                'name': etapa_data.get('name', f'Etapa {idx+1}'),
                'description': etapa_data.get('description'),
                'percent_weight': float(etapa_data.get('weight', 0.0)),
                'sequence': etapa_data.get('sequence', (idx+1)*10),
                'state': 'planning',
            })
            etapas_map[idx] = stage.id

        # 4. Crear Capítulo Único (por ahora, para simplificar)
        chapter = self.env['building.budget.chapter'].create({
            'budget_id': budget.id,
            'code': 'CAP-01',
            'name': 'Conceptos Generales',
            'sequence': 10
        })

        # 5. Crear Partidas
        for idx, line_data in enumerate(data.get('partidas', [])):
            # Resolver unidad
            uom = self._find_or_create_uom(line_data.get('unit'))
            
            # Resolver etapa
            stage_id = False
            etapa_idx = line_data.get('etapa_idx')
            if etapa_idx is not None and etapa_idx in etapas_map:
                stage_id = etapas_map[etapa_idx]
            
            # Calcular montos
            qty = float(line_data.get('quantity', 1.0))
            price = float(line_data.get('unit_price', 0.0))
            amount = qty * price if price > 0 else float(line_data.get('amount', 0.0))
            
            line_vals = {
                'chapter_id': chapter.id,
                'code': str(line_data.get('code', idx + 1)),
                'name': line_data.get('name', f'Partida {idx+1}'),
                'quantity': qty,
                'unit_price': price,
                'amount': amount,
                'product_uom_id': uom.id if uom else False,
                'stage_id': stage_id, # Asignación directa a etapa (Fase 3.3)
                'sequence': (idx + 1) * 10,
                'period_from': int(line_data.get('period_from', 1)),
                'period_to': int(line_data.get('period_to', 1)),
            }
            self.env['building.budget.line'].create(line_vals)
            
        return work

    def _reload_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.ai.chat',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

class BuildingAIChatMessage(models.Model):
    _name = 'building.ai.chat.message'
    _description = 'Mensaje de Chat IA'
    _order = 'create_date asc'
    
    chat_id = fields.Many2one('building.ai.chat', string='Chat', required=True, ondelete='cascade')
    role = fields.Selection([('user', 'Usuario'), ('assistant', 'IA')], required=True)
    content = fields.Text(required=True)
    has_generation = fields.Boolean(default=False)
