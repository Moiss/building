# -*- coding: utf-8 -*-
import re
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BuildingAIChat(models.Model):
    _name = 'building.ai.chat'
    _description = 'Chat IA para Generación de Obras'
    _inherit = ['mail.thread']

    name = fields.Char(string='Título', default='Nuevo Chat', required=True)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, required=True)

    chat_history_ids = fields.One2many(
        'building.ai.chat.message',
        'chat_id',
        string='Historial de Conversación'
    )

    user_input = fields.Text(string='Mensaje')
    last_response = fields.Text(string='Última Respuesta')
    generated_json = fields.Text(string='JSON Generado')

    # === CORRECCIÓN 3: Campo de adjuntos temporales ===
    user_attachment_ids = fields.Many2many(
        'ir.attachment',
        'building_ai_chat_attachment_rel',
        'chat_id',
        'attachment_id',
        string='Adjuntar planos/archivos',
        help='Sube planos o documentos para mejorar el presupuesto'
    )

    state = fields.Selection([
        ('draft', 'Planeada'),
        ('ready', 'Propuesta Lista'),
        ('created', 'Creada')
    ], string='Estado', default='draft', required=True)

    has_generated_work = fields.Boolean(string='Tiene Obra Generada', default=False)
    generated_work_id = fields.Many2one('building.work', string='Obra Generada')

    def action_send_message(self):
        """Envía el mensaje al servicio de IA configurado."""
        self.ensure_one()
        if not self.user_input:
            raise UserError(_('Por favor escriba un mensaje antes de enviar.'))

        # === CORRECCIÓN 3: Procesar adjuntos si existen ===
        attachment_note = ''
        system_attachment_note = ''
        if self.user_attachment_ids:
            names = ', '.join(self.user_attachment_ids.mapped('name'))
            attachment_note = f'\n[Archivos adjuntos: {names}]'
            system_attachment_note = (
                '\nEl usuario ha adjuntado planos/documentos. '
                'Considera que la obra tiene planos disponibles '
                'y ajusta el presupuesto con mayor precisión.'
            )

        # 1. Guardar mensaje de usuario (con referencia a adjuntos)
        user_content = self.user_input + attachment_note
        user_msg = self.env['building.ai.chat.message'].create({
            'chat_id': self.id,
            'role': 'user',
            'content': user_content,
        })

        # Vincular adjuntos al mensaje del usuario
        if self.user_attachment_ids:
            user_msg.attachment_ids = [(6, 0, self.user_attachment_ids.ids)]

        # 2. Preparar contexto
        history = []
        for msg in self.chat_history_ids.sorted('id'):
            history.append({'role': msg.role, 'content': msg.content})

        system_prompt = self._get_system_prompt() + system_attachment_note

        # 3. Llamar al servicio
        service = self.env['building.ai.service']
        try:
            ai_response = service.send_message(history, system_prompt, work_id=False)

            # === CORRECCIÓN 2: Parsear JSON del texto ORIGINAL, luego limpiar para display ===
            # Parsear primero (preserva JSON para crear la obra)
            if '```json' in ai_response:
                try:
                    start = ai_response.find('```json') + 7
                    end = ai_response.find('```', start)
                    self.generated_json = ai_response[start:end].strip()
                    self.state = 'ready'
                except Exception as e:
                    _logger.error("Error extracting JSON: %s", str(e))

            # Limpiar respuesta para display (ocultar bloque JSON técnico)
            display_response = self._clean_ai_response_for_display(ai_response)

            # 4. Guardar versión LIMPIA en el chat (sin bloque JSON crudo)
            self.env['building.ai.chat.message'].create({
                'chat_id': self.id,
                'role': 'assistant',
                'content': display_response,
                'has_generation': ('```json' in ai_response),
            })

            self.last_response = ai_response
            self.user_input = False

            # === CORRECCIÓN 3: Limpiar adjuntos temporales después de enviar ===
            self.user_attachment_ids = [(5, 0, 0)]

            # 5. Recargar UI para mostrar mensajes
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Respuesta de IA'),
                    'message': _('La IA ha respondido.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                }
            }

        except Exception as e:
            _logger.error("Error en Chat IA: %s", str(e))
            raise UserError(_('Error al comunicarse con la IA: %s') % str(e))

    def action_create_work(self):
        """Crea la obra a partir del JSON guardado."""
        self.ensure_one()
        if not self.generated_json:
            raise UserError(_('No hay una propuesta de obra válida para crear.'))

        try:
            data = json.loads(self.generated_json)
            work = self._create_work_from_json(data)
            if work:
                self.generated_work_id = work.id
                self.has_generated_work = True
                self.state = 'created'

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Obra Creada'),
                        'message': _('Se ha creado la obra "%s" satisfactoriamente.') % work.name,
                        'type': 'success',
                        'sticky': False,
                        'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                    }
                }
        except Exception as e:
            _logger.error("Error creating work from JSON: %s", str(e))
            raise UserError(_('Error al procesar el JSON de la obra: %s') % str(e))

    def action_view_generated_work(self):
        """Abre la vista de la obra generada."""
        self.ensure_one()
        if not self.generated_work_id:
            raise UserError(_('No hay una obra generada para este chat.'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'building.work',
            'res_id': self.generated_work_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # === CORRECCIÓN 2: Helper para limpiar JSON del display ===
    def _clean_ai_response_for_display(self, text):
        """Reemplaza bloque JSON técnico por mensaje amigable."""
        pattern = r"```(?:json)?\s*\{.*?\}\s*```"
        replacement = (
            "\n\n✅ Propuesta lista. "
            "Haz clic en **Crear Obra** para generarla en Odoo."
        )
        cleaned = re.sub(pattern, replacement, text, flags=re.DOTALL)
        return cleaned.strip()

    def _get_system_prompt(self):
        """Retorna el prompt conversacional de 5 turnos para generación de obras."""
        return """ERES UN EXPERTO ARQUITECTO Y GERENTE DE OBRA DE MÉXICO.
Tu rol es ayudar al usuario a planificar y presupuestar obras de construcción.

PRECIOS Y MERCADO:
- Usa precios realistas para México en 2026 (MXN).
- Considera mano de obra, materiales y equipo por separado.

═══════════════════════════════════════
FLUJO OBLIGATORIO DE CONVERSACIÓN (5 TURNOS)
═══════════════════════════════════════

TURNO 1 — Si el usuario menciona una obra por primera vez:
  Haz EXACTAMENTE estas 3 preguntas en un solo mensaje:
  1. ¿Cuál es la superficie o dimensión aproximada (m², ml, piezas)?
  2. ¿En qué municipio/estado se realizará?
  3. ¿Cuál es el plazo esperado de ejecución en meses?

TURNO 2 — Con las respuestas del usuario:
  Si alguna respuesta es vaga, pide aclaración específica.
  Si tienes suficiente información, avanza al Turno 3.

TURNO 3 — Propuesta inicial (SOLO TEXTO, SIN JSON):
  Presenta un resumen estructurado con este formato exacto:

  📋 PROPUESTA DE OBRA: [Nombre]
  ─────────────────────────────
  📍 Ubicación: [lugar]
  📅 Duración estimada: [N] meses
  💰 Presupuesto total estimado: $[monto] MXN

  ETAPAS PROPUESTAS:
  • [Etapa 1] — $[monto] ([X]% del total)
  • [Etapa 2] — $[monto] ([X]% del total)
  • [Etapa 3] — $[monto] ([X]% del total)

  CONCEPTOS PRINCIPALES:
  • [Concepto A]: [cant] [ud] × $[precio] = $[subtotal]
  • [Concepto B]: [cant] [ud] × $[precio] = $[subtotal]
  • [Concepto C]: [cant] [ud] × $[precio] = $[subtotal]

  ¿Deseas agregar, eliminar o modificar algún concepto o etapa
  antes de crear la obra en el sistema?

TURNO 4 — Ajustes (SOLO TEXTO, SIN JSON):
  Si el usuario pide cambios, aplícalos y repite el resumen actualizado.
  Si el usuario confirma que está de acuerdo sin cambios, avanza.

TURNO 5 — Generación del JSON (SOLO si el usuario confirmó en Turno 4):
  Frases que indican confirmación: "sí", "adelante", "conforme",
  "está bien", "genéralo", "créalo", "procede", "de acuerdo".
  Genera el bloque JSON con TODOS los conceptos desglosados.

═══════════════════════════════════════
FORMATO JSON (solo en Turno 5)
═══════════════════════════════════════

```json
{
  "name": "Nombre del Proyecto",
  "duration_months": 3,
  "etapas": [
    {
      "name": "Cimentación",
      "description": "Excavación y colado de zapatas",
      "sequence": 10,
      "weight": 20.0
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
    }
  ]
}
```

REGLAS ESTRICTAS:
1. NUNCA generes el JSON antes de que el usuario confirme el resumen textual.
2. NUNCA saltes pasos del flujo.
3. "partidas" deben incluir: unit, quantity, unit_price, amount, period_from, period_to, etapa_idx.
4. Los pesos de etapas deben sumar exactamente 100.
5. SIEMPRE responde en español profesional.
"""

    def _safe_str(self, val, default=''):
        """Convierte un valor a str de forma segura."""
        try:
            return str(val).strip() if val is not None else default
        except Exception:
            return default

    def _safe_float(self, val, default=0.0):
        """Convierte un valor a float de forma segura."""
        try:
            return float(val or 0)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, val, default=0):
        """Convierte un valor a int de forma segura."""
        try:
            return int(val or 0)
        except (TypeError, ValueError):
            return default

    def _create_work_from_json(self, data):
        """Crea obra desde JSON de IA. Solo usa campos verificados.
        Cualquier campo extra generado por la IA (uom.category, date_start,
        description en work, total_budget, duration_months, etc.) es ignorado.
        """
        # Compatibilidad: la IA puede envolver datos en 'obra'
        obra_data = data.get('obra', data)

        # ── 1. OBRA — solo name y company_id ──────────────────────────
        work = self.env['building.work'].create({
            'name': self._safe_str(obra_data.get('name'), 'Obra IA'),
            'company_id': self.env.company.id,
        })

        # ── 2. PRESUPUESTO — solo campos verificados ──────────────────
        presup_data = data.get('presupuesto', {})
        budget = self.env['building.budget'].create({
            'work_id': work.id,
            'name': self._safe_str(
                presup_data.get('name'), f'Presupuesto {work.name}'
            ),
            'budget_type': 'base',
        })

        # ── 3. ETAPAS ─────────────────────────────────────────────────
        etapas_map = {}  # index -> stage_id
        for idx, et in enumerate(data.get('etapas', [])):
            stage = self.env['building.work.stage'].create({
                'work_id': work.id,
                'name': self._safe_str(et.get('name'), f'Etapa {idx + 1}'),
                'sequence': self._safe_int(et.get('sequence'), (idx + 1) * 10),
                'state': 'planning',
            })
            etapas_map[idx] = stage.id

        # ── 4. CAPÍTULOS Y PARTIDAS ───────────────────────────────────
        # Soporta tanto estructura con 'capitulos' como 'partidas' planas
        capitulos = data.get('capitulos', [])

        if not capitulos:
            # Fallback: crear un capítulo único con todas las partidas
            capitulos = [{
                'code': 'CAP-01',
                'name': 'Conceptos Generales',
                'sequence': 10,
                'partidas': data.get('partidas', []),
            }]

        for cap_idx, cap in enumerate(capitulos):
            chapter = self.env['building.budget.chapter'].create({
                'budget_id': budget.id,
                'code': self._safe_str(
                    cap.get('code'), 'CAP-%02d' % (cap_idx + 1)
                ),
                'name': self._safe_str(
                    cap.get('name'), 'Capítulo %d' % (cap_idx + 1)
                ),
                'sequence': self._safe_int(
                    cap.get('sequence'), (cap_idx + 1) * 10
                ),
            })

            for line_idx, line in enumerate(cap.get('partidas', [])):
                # Calcular amount de forma segura, buscando cualquier clave
                amount = 0.0
                for key in ('amount', 'total', 'costo', 'importe', 'monto'):
                    if key in line:
                        amount = self._safe_float(line[key])
                        break
                # Si qty * price es más confiable, usarlo
                qty = self._safe_float(line.get('quantity'), 1.0)
                price = self._safe_float(line.get('unit_price'))
                if price > 0:
                    amount = qty * price

                # Resolver etapa por índice (etapa_idx) si existe
                stage_id = False
                etapa_idx = line.get('etapa_idx')
                if etapa_idx is not None:
                    stage_id = etapas_map.get(self._safe_int(etapa_idx))

                self.env['building.budget.line'].create({
                    'chapter_id': chapter.id,
                    'code': self._safe_str(
                        line.get('code'), str(line_idx + 1)
                    ),
                    'name': self._safe_str(
                        line.get('name'), f'Partida {line_idx + 1}'
                    ),
                    'amount': amount,
                    'sequence': self._safe_int(
                        line.get('sequence'), (line_idx + 1) * 10
                    ),
                    'stage_id': stage_id or False,
                    'period_from': self._safe_int(line.get('period_from'), 1),
                    'period_to': self._safe_int(line.get('period_to'), 1),
                })

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

    # === CORRECCIÓN 3: Adjuntos vinculados al mensaje ===
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'building_ai_message_attachment_rel',
        'message_id',
        'attachment_id',
        string='Archivos adjuntos'
    )
