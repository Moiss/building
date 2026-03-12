# CONTEXTO MAESTRO — OdooBuilding
**Proyecto:** building_dashboard (Odoo 19 CE)
**Developer:** Mois — NextPack, Zapopan Jalisco MX
**Fecha:** 2026-02-28

---

## DESCRIPCIÓN DEL SISTEMA

OdooBuilding es un módulo de Odoo 19 CE para control de obras
de construcción en México. Maneja presupuestos, avance físico,
gastos reales, facturas CFDI, analítica y un asistente IA
conversacional que genera obras completas desde un chat.

**Stack técnico:**
- Backend: Python, Odoo 19 CE, MariaDB
- Vistas: XML (Odoo views)
- IA: Claude Anthropic, Gemini, ChatGPT (3 proveedores)
- IDE: Antigravity
- Ruta local: `/Users/macbookpro/odoo/odoo19ce/proyectos/building_dashboard`
- Base de datos: `building_dashboard`

---

## ROADMAP COMPLETO

### ✅ TERMINADAS

| Etapa | Nombre |
|---|---|
| 0 | Bootstrap / Base (building.work, menús, catálogos) |
| 1 | Presupuesto estructurado (partidas, importes, anticipos) |
| 2 | Planeación de Etapas/Fases con fechas y semáforos |
| 3.1 | Dashboard + KPIs + Alertas automáticas |
| 3.2 | Avance físico por etapas |
| 3.3 | Semáforos + Drilldowns + Normalización |
| 4.1 | Gastos Adicionales / Costos Operativos |
| 4.2 | Evidencias de Obra (fotos/documentos) |
| 4.3a | Presupuestos Múltiples (base + extras/adendas) |
| 4.3b | Wizard de Consolidación (merge automático) |
| 4.4a | Distribución de Facturas → Obras |
| 4.4b | Contabilidad Analítica por Obra |
| 4.4c | Carga CFDI XML (validación SAT 4.0) |
| 4.6 | Identificador Obra Pública / Contrato |
| 4.7 | Reporte Paramétrico Financiero (vista + Excel) |
| 5.1 | Asistente IA Chat Conversacional (Claude/Gemini/GPT) |
| Fix 5.1b | _create_work_from_json() defensivo — 5 bugs corregidos |
| Fix 5.1c | UI: botones redundantes eliminados, tab Claude habilitado |

### 🔄 EN CURSO

| Etapa | Nombre | Notas |
|---|---|---|
| 4.5 | Jornales / Mano de Obra | SDD v2 aprobado — en implementación |

### ⏳ PENDIENTES

| Etapa | Nombre | Notas |
|---|---|---|
| 5.2 | Flujo de aprobación de gastos | Prioridad 1 |
| 5.3 | Fechas y alertas por etapa | Prioridad 2 |
| 5.4 | Vista resumen granular por fase/concepto (Sábana) | Prioridad 3 |
| 5.5 | Perfiles y Permisos (roles) | Prioridad 4 |
| 5.6 | Change Orders (Aditivas-Deductivas) | Gap vs OPUS M2 |
| 5.7 | Ejecución vs Oferta (escenario margen) | Gap vs OPUS M2 |
| 3.2-Ma | Avance físico por partida individual — modelo | Prereq 5.8/5.9 |
| 3.2-Mb | Avance físico por partida — vistas y UI | Prereq 5.8/5.9 |
| 3.2-Mc | Avance físico por partida — KPIs y dashboard | Prereq 5.8/5.9 |
| 5.8 | Explosión de Insumos / Monitor Rendimientos (APU) | Depende 3.2-M |
| 5.9 | Portal Residente | Depende 3.2-M |
| 5.10 | TBD — Gap analysis OPUS M2 | Por definir |
| 5.11 | TBD — Gap analysis OPUS M2 | Por definir |
| 4.5b | Conectar Jornales → building.real.line (gastos reales) | Puente futuro |
| **6.0** | **Release Hardening / Limpieza Pre-Producción** | **Última etapa obligatoria** |

### 📋 Etapa 6.0 — Release Hardening (detalle)

| Sub-tarea | Descripción |
|---|---|
| 6.0-A | Limpiar código: eliminar prints, debugs, TODOs, archivos temporales |
| 6.0-B | Limpiar base de datos: datos de prueba, ir.logging, vacuum MariaDB |
| 6.0-C | Verificar seguridad: accesos CSV, grupos, API keys hardcodeadas |
| 6.0-D | Prueba de upgrade limpio sobre base vacía |
| 6.0-E | Git: merge a main, tag v1.0.0, limpiar branches viejas |
| 6.0-F | Documentación: README instalación, guía de API keys, contexto maestro final |

---

## MODELOS PRINCIPALES

```
building.work              — Obra principal
building.budget            — Presupuesto (base/extra/consolidado)
building.budget.chapter    — Capítulo del presupuesto
building.budget.line       — Partida (code, name, amount, period_from int, period_to int)
building.work.stage        — Etapa/Fase (state: planning/in_progress/to_approve/done)
building.real.line         — Gasto real
building.work.cost         — Costo adicional/indirecto
building.work.evidence     — Evidencia fotográfica
building.bill.allocation   — Distribución de factura a obra
building.ai.chat           — Chat IA (state: draft/generated)
building.ai.chat.message   — Mensaje del chat (role: user/assistant)
building.ai.config         — Configuración de API keys IA
building.ai.config.wizard  — Wizard configuración (claude_model, gemini_model, openai_model)
```

**Campos críticos verificados:**
- `building.budget.line`: NO tiene unit_id, quantity, unit_price. period_from/to son Integer.
- `building.work.stage`: state válido = 'planning' (NO 'planned'). NO tiene percent_weight.
- `building.ai.config.wizard`: usa `claude_status` (no claude_state) y `claude_last4` (no claude_key_last4)

---

## MODELOS DE IA CONFIGURADOS

### Claude (Anthropic)
```python
('claude-opus-4-6', 'Claude Opus 4.6')
('claude-opus-4-5-20251101', 'Claude Opus 4.5')
('claude-sonnet-4-6', 'Claude Sonnet 4.6') ← default
('claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5')
('claude-haiku-4-5-20251001', 'Claude Haiku 4.5')
```

### Gemini (Google)
```python
('gemini-3-pro-preview', 'Gemini 3 Pro')
('gemini-3-flash-preview', 'Gemini 3 Flash') ← default
('gemini-2.5-pro', 'Gemini 2.5 Pro')
('gemini-2.5-flash', 'Gemini 2.5 Flash')
('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite')
```

### OpenAI
```python
('gpt-5.2', 'GPT-5.2 Thinking')
('gpt-5.2-pro', 'GPT-5.2 Pro')
('gpt-5.2-chat-latest', 'GPT-5.2 Instant') ← default
('gpt-5-mini', 'GPT-5 Mini')
```

---

## REGLAS DE DESARROLLO

1. **Formato SDD** tabular con schemas, contratos API y acceptance criteria numerados
2. **GIT:** branch por etapa (`fix-5.1-F1-chat-ui`), merge a main al completar, sin push hasta orden
3. **Nunca modificar modelos nativos Odoo** — siempre extender con `_inherit`
4. **Odoo 19 CE:** usar `<list>` NO `<tree>`, sin `attrs=""` deprecated, sin `expand="1"`
5. **Idioma:** Todo en español — código, comentarios, tasks, walkthrough, thoughts, implementation plan
6. **Antigravity:** Primero diagnóstico (solo lectura), luego fix certero
7. **Context Blueprint para Gemini** obligatorio al final de cada SDD

---

## ESTRUCTURA SDD ESTÁNDAR

```markdown
# SDD — Etapa X.X: Nombre
Módulo, Fecha, Prioridad (@high/@low), Branch GIT

## GIT (solo primer prompt de etapa)
## PROBLEMA
## SOLUCIÓN
## CAMBIOS (tablas de campos, contratos API)
## ACCEPTANCE CRITERIA (AC-01, AC-02...)
## UPGRADE (comando)
## 🛠 Context Blueprint para Gemini
  - Modelos _name
  - File Manifest (ruta + Crear/Modificar)
  - Decoradores + campos
  - Seguridad (access.csv + groups)
  - Manifest Update
```

---

## UPGRADE COMMAND

```bash
python odoo-bin \
  -c /Users/macbookpro/odoo/odoo19ce/proyectos/building_dashboard/odoo.conf \
  -d building_dashboard \
  -u building_dashboard
```

---

## COMPORTAMIENTO DEL ASISTENTE IA (building_ai_chat.py)

**Flujo conversacional (system prompt):**
1. Turno 1: Pregunta tipo de obra
2. Turno 2: Superficie y municipio
3. Turno 3: Niveles, distribución, acabados
4. Turno 4: Resumen textual con desglose + confirmación
5. Turno 5: Solo si confirma → genera JSON → crea obra

**_create_work_from_json() — campos permitidos:**
```python
building.work:          name, company_id
building.budget:        work_id, name, budget_type='base'
building.budget.chapter: budget_id, code, name, sequence
building.budget.line:   chapter_id, code, name, amount, sequence, period_from(int), period_to(int)
building.work.stage:    work_id, name, sequence, state='planning'
```

---

## PRÓXIMOS PASOS INMEDIATOS

1. ⏳ Terminar Etapa 4.5 — Jornales (SDD v2 en Antigravity)
2. ⏳ Arrancar Etapa 5.2 — Flujo aprobación de gastos
3. ⏳ Etapa 6.0 — Release Hardening al finalizar todo el roadmap
