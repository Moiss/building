# -*- coding: utf-8 -*-
import json
import re
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BuildingAIChat(models.Model):
    _name = 'building.ai.chat'
    _description = 'Chat Asistente IA Generador'
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    
    state = fields.Selection([
        ('active', 'Activo'),
        ('generated', 'Obra Generada'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='active', readonly=True)
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    message_ids = fields.One2many(
        'building.ai.chat.message',
        'chat_id',
        string='Mensajes'
    )
    
    work_id = fields.Many2one(
        'building.work',
        string='Obra Generada',
        readonly=True
    )
    
    user_input = fields.Text(string='Escribe tu mensaje...')
    
    generated_json = fields.Text(string='JSON Generado', readonly=True)

    @api.depends('create_date')
    def _compute_name(self):
        for record in self:
            date_str = record.create_date.strftime('%d/%m/%Y %H:%M') if record.create_date else 'Nuevo'
            record.name = f"Chat IA - {date_str}"

    def action_send_message(self):
        """
        Envía el mensaje del usuario a la IA y procesa la respuesta.
        """
        self.ensure_one()
        if not self.user_input:
            raise UserError(_("Por favor escribe un mensaje."))
        
        prompt = self.user_input
        
        # 1. Guardar mensaje usuario
        self.env['building.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'user',
            'content': prompt
        })
        
        # 2. Construir historial
        # Filtrar solo mensajes útiles
        messages_history = []
        for msg in self.message_ids.sorted('create_date'):
            messages_history.append({
                'role': msg.role,
                'content': msg.content
            })
            
        # 3. Obtener System Prompt
        system_prompt = self._get_system_prompt()
        
        # 4. Llamar al servicio IA
        service = self.env['building.ai.service']
        try:
            ai_response = service.send_message(messages_history, system_prompt, work_id=False)
        except Exception as e:
            # Registrar error como mensaje del sistema/asistente
            error_text = f"❌ Error: {str(e)}"
            self.env['building.ai.chat.message'].create({
                'chat_id': self.id,
                'role': 'assistant',
                'content': error_text
            })
            self.user_input = False
            return self._reload_form()

        # 5. Guardar respuesta IA
        self.env['building.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'assistant',
            'content': ai_response
        })
        
        # 6. Parsear posible JSON
        json_data = self._parse_ai_response(ai_response)
        
        action = False
        if json_data:
            # Generar Obra
            try:
                action = self._create_work_from_json(json_data)
                # Marcar mensaje como que tuvo generación
                last_msg = self.message_ids.sorted('create_date')[-1]
                last_msg.has_generation = True
            except Exception as e:
                 _logger.error("Error generando obra desde JSON: %s", str(e))
                 self.env['building.ai.chat.message'].create({
                    'chat_id': self.id,
                    'role': 'assistant',
                    'content': f"⚠️ Error al generar la obra: {str(e)}. Intenta pedirle a la IA que corrija el formato."
                })

        # 7. Limpiar input y recargar
        self.user_input = False
        return action if action else self._reload_form()

    def _get_system_prompt(self):
        return """
Eres un asistente experto en construcción y presupuestos de obra
en México. Tu rol es ayudar a generar presupuestos paramétricos
completos para obras de construcción.

PROCESO DE CONVERSACIÓN:
1. Saluda brevemente y pregunta qué tipo de obra quiere realizar
2. Pregunta detalles clave: superficie, ubicación, niveles, acabados
3. Haz preguntas de seguimiento para afinar (2-3 turnos máximo)
4. Presenta un RESUMEN de lo que vas a generar con estimado de costo
5. Si el usuario confirma, genera el JSON

DATOS QUE DEBES RECOPILAR:
- Tipo de obra (casa, edificio, nave industrial, plaza comercial,
  carretera, puente, escuela, hospital)
- Superficie m² (construcción y terreno)
- Número de niveles/pisos
- Distribución (recámaras, baños, cochera, áreas comunes)
- Ubicación (estado/ciudad para costos regionales)
- Nivel de acabados (económico, medio, premium)
- Presupuesto máximo disponible (si lo tiene)
- Si es obra pública: tipo de contratación, dependencia, alcance

COSTOS DE REFERENCIA MÉXICO 2025-2026 (por m² construido):
- Económico: $8,000 - $12,000 MXN/m²
- Medio: $12,000 - $18,000 MXN/m²
- Premium: $18,000 - $30,000 MXN/m²
Ajustar +10-15% para CDMX/Monterrey, -5-10% ciudades medianas.

CAPÍTULOS TÍPICOS CASA HABITACIÓN:
1. PRELIMINARES (trazo, limpieza, nivelación)
2. CIMENTACIÓN (excavación, zapatas, contratrabes, firmes)
3. ESTRUCTURA (columnas, trabes, losas, escaleras)
4. ALBAÑILERÍA (muros, castillos, cerramientos, pretiles)
5. INSTALACIÓN HIDRÁULICA Y SANITARIA
6. INSTALACIÓN ELÉCTRICA
7. ACABADOS (pisos, muros, plafones, pintura)
8. CARPINTERÍA Y HERRERÍA (puertas, ventanas, closets, barandales)
9. OBRAS EXTERIORES (jardín, cochera, barda, cisterna)
10. LIMPIEZA Y VARIOS

ETAPAS TÍPICAS CON PESOS:
1. Cimentación (20-25%)
2. Estructura (25-30%)
3. Albañilería e Instalaciones (20-25%)
4. Acabados (15-20%)
5. Obras Exteriores y Limpieza (5-10%)

CUANDO EL USUARIO CONFIRME EXPLÍCITAMENTE (diga "sí", "genera",
"adelante", "ok", "listo", etc.), responde con un texto breve
confirmando Y AL FINAL incluye un bloque JSON entre marcadores
```json ... ``` con esta estructura EXACTA:

```json
{
  "obra": { "name": "Casa Habitación - León Gto", "work_type": "private" },
  "presupuesto": {
    "name": "Presupuesto Base - IA",
    "budget_type": "base",
    "duration_months": 12
  },
  "capitulos": [
    {
      "code": "CAP-01",
      "name": "PRELIMINARES",
      "sequence": 10,
      "partidas": [
        {
          "code": "P-001",
          "name": "Trazo Y Nivelación",
          "amount": 8100.00,
          "period_from": 1,
          "period_to": 1
        }
      ]
    }
  ],
  "etapas": [
    { "name": "Cimentación", "weight": 25.0, "sequence": 10,
      "description": "Excavación, zapatas y cimientos" }
  ]
}
```

REGLAS ESTRICTAS:
- Genera entre 6-10 capítulos según el tipo de obra
- Genera entre 30-60 partidas distribuidas en los capítulos
- period_from y period_to son ENTEROS (mes 1, 2, 3... N)
  donde N = presupuesto.duration_months. NUNCA fechas YYYY-MM-DD
- Las etapas DEBEN tener pesos que sumen EXACTAMENTE 100%
- El total debe cuadrar con el nivel de acabados × m²
- SOLO genera el JSON cuando el usuario confirme explícitamente
- Si el usuario pide ajustes, modifica y genera de nuevo
- Responde SIEMPRE en español
- work_type: "private" para obra privada, "public" para pública
- NO incluyas quantity, unit_price, unit, unit_id en las partidas
- SIEMPRE incluir duration_months en el objeto "presupuesto"
"""

    def _parse_ai_response(self, text):
        """Busca y parsea JSON en la respuesta."""
        # Regex para buscar ```json ... ``` o ``` ... ```
        pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None
        return None

    def _create_work_from_json(self, data):
        """
        Crea obra completa desde JSON generado por IA.
        
        Mapeo verificado contra modelos reales:
        - building.budget.line: solo chapter_id, code, name, amount,
          sequence, period_from (int), period_to (int)
        - building.work.stage: solo work_id, name, sequence, state='planning'
        - budget_id y work_id en line son related readonly → no se pasan
        """
        # 1. Obra
        obra_data = data.get('obra', {})
        work_vals = {
            'name': obra_data.get('name', 'Obra Generada IA'),
            'company_id': self.env.company.id,
        }
        if 'work_type' in self.env['building.work']._fields:
            work_vals['work_type'] = obra_data.get('work_type', 'private')
        work = self.env['building.work'].create(work_vals)

        # 2. Presupuesto
        budget = self.env['building.budget'].create({
            'work_id': work.id,
            'name': data.get('presupuesto', {}).get('name', 'Presupuesto IA'),
            'budget_type': 'base',
        })

        # 3. Capítulos y Partidas
        # Calcular periodos enteros secuenciales por capítulo
        # (la IA puede generar fechas, aquí siempre usamos enteros)
        capitulos = data.get('capitulos', [])
        for cap_idx, cap_data in enumerate(capitulos):
            p_from = (cap_idx * 2) + 1
            p_to = p_from + 1

            chapter = self.env['building.budget.chapter'].create({
                'budget_id': budget.id,
                'code': cap_data.get('code', 'CAP-%02d' % (cap_idx + 1)),
                'name': cap_data.get('name', 'Capítulo %d' % (cap_idx + 1)),
                'sequence': cap_data.get('sequence', (cap_idx + 1) * 10),
            })

            for idx, line_data in enumerate(cap_data.get('partidas', [])):
                self.env['building.budget.line'].create({
                    'chapter_id': chapter.id,
                    # budget_id y work_id son related readonly → NO se pasan
                    # unit_id, quantity, unit_price → NO EXISTEN en el modelo
                    'code': str(line_data.get('code', idx + 1)),
                    'name': line_data.get('name', 'Partida %d' % (idx + 1)),
                    'amount': float(line_data.get('amount', 0.0) or 0.0),
                    'sequence': (idx + 1) * 10,
                    'period_from': p_from,
                    'period_to': p_to,
                })

        # 4. Etapas
        # percent_weight y description NO EXISTEN en building.work.stage
        # state válido = 'planning' (NO 'planned')
        for etapa_data in data.get('etapas', []):
            self.env['building.work.stage'].create({
                'work_id': work.id,
                'name': etapa_data.get('name', 'Etapa'),
                'sequence': etapa_data.get('sequence', 10),
                'state': 'planning',
            })

        # 5. Actualizar estado del chat
        self.write({
            'state': 'generated',
            'work_id': work.id,
            'generated_json': json.dumps(data, indent=2, ensure_ascii=False),
        })
        return self.action_view_generated_work()



    def action_view_generated_work(self):
        self.ensure_one()
        if not self.work_id: return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.work',
            'res_id': self.work_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _reload_form(self):
        """Recarga el chat abriendo el mismo registro en form."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.ai.chat',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_system_prompt(self):
        return """
Eres un asistente experto en construcción y presupuestos de obra
en México. Tu rol es ayudar a generar presupuestos paramétricos
completos para obras de construcción.

PROCESO DE CONVERSACIÓN:
1. Saluda brevemente y pregunta qué tipo de obra quiere realizar
2. Pregunta detalles clave: superficie, ubicación, niveles, acabados
3. Haz preguntas de seguimiento para afinar (2-3 turnos máximo)
4. Presenta un RESUMEN de lo que vas a generar con estimado de costo
5. Si el usuario confirma, genera el JSON

DATOS QUE DEBES RECOPILAR:
- Tipo de obra (casa, edificio, nave industrial, plaza comercial,
  carretera, puente, escuela, hospital)
- Superficie m² (construcción y terreno)
- Número de niveles/pisos
- Distribución (recámaras, baños, cochera, áreas comunes)
- Ubicación (estado/ciudad para costos regionales)
- Nivel de acabados (económico, medio, premium)
- Presupuesto máximo disponible (si lo tiene)
- Si es obra pública: tipo de contratación, dependencia, alcance

COSTOS DE REFERENCIA MÉXICO 2025-2026 (por m² construido):
- Económico: $8,000 - $12,000 MXN/m²
- Medio: $12,000 - $18,000 MXN/m²
- Premium: $18,000 - $30,000 MXN/m²
Ajustar +10-15% para CDMX/Monterrey, -5-10% ciudades medianas.

CAPÍTULOS TÍPICOS CASA HABITACIÓN:
1. PRELIMINARES (trazo, limpieza, nivelación)
2. CIMENTACIÓN (excavación, zapatas, contratrabes, firmes)
3. ESTRUCTURA (columnas, trabes, losas, escaleras)
4. ALBAÑILERÍA (muros, castillos, cerramientos, pretiles)
5. INSTALACIÓN HIDRÁULICA Y SANITARIA
6. INSTALACIÓN ELÉCTRICA
7. ACABADOS (pisos, muros, plafones, pintura)
8. CARPINTERÍA Y HERRERÍA (puertas, ventanas, closets, barandales)
9. OBRAS EXTERIORES (jardín, cochera, barda, cisterna)
10. LIMPIEZA Y VARIOS

ETAPAS TÍPICAS CON PESOS:
1. Cimentación (20-25%)
2. Estructura (25-30%)
3. Albañilería e Instalaciones (20-25%)
4. Acabados (15-20%)
5. Obras Exteriores y Limpieza (5-10%)

CUANDO EL USUARIO CONFIRME EXPLÍCITAMENTE (diga "sí", "genera",
"adelante", "ok", "listo", etc.), responde con un texto breve
confirmando Y AL FINAL incluye un bloque JSON entre marcadores
```json ... ``` con esta estructura EXACTA:

```json
{
  "obra": { "name": "Casa Habitación - León Gto", "work_type": "private" },
  "presupuesto": {
    "name": "Presupuesto Base - IA",
    "budget_type": "base",
    "duration_months": 12
  },
  "capitulos": [
    {
      "code": "CAP-01",
      "name": "PRELIMINARES",
      "sequence": 10,
      "partidas": [
        {
          "code": "P-001",
          "name": "Trazo Y Nivelación",
          "amount": 8100.00,
          "period_from": 1,
          "period_to": 2
        }
      ]
    }
  ],
  "etapas": [
    { "name": "Cimentación", "sequence": 10 }
  ]
}
```

REGLAS ESTRICTAS:
- Genera entre 6-10 capítulos según el tipo de obra
- Genera entre 30-60 partidas distribuidas en los capítulos
- period_from y period_to son ENTEROS (1, 2, 3...) NUNCA fechas YYYY-MM-DD
- Las etapas DEBEN tener pesos que sumen EXACTAMENTE 100%
- El total debe cuadrar con el nivel de acabados × m²
- SOLO genera el JSON cuando el usuario confirme explícitamente
- Si el usuario pide ajustes, modifica y genera de nuevo
- Responde SIEMPRE en español
- work_type: "private" para obra privada, "public" para pública
- SIEMPRE incluir duration_months en el objeto "presupuesto"
- Las partidas solo necesitan: code, name, amount (sin unit, quantity, unit_price)
- Las etapas solo necesitan: name, sequence (sin weight, description)
"""

class BuildingAIChatMessage(models.Model):
    _name = 'building.ai.chat.message'
    _description = 'Mensaje de Chat IA'
    _order = 'create_date asc'
    
    chat_id = fields.Many2one('building.ai.chat', string='Chat', required=True, ondelete='cascade')
    role = fields.Selection([('user', 'Usuario'), ('assistant', 'IA')], required=True)
    content = fields.Text(required=True)
    has_generation = fields.Boolean(default=False)
