# CONTEXTO MAESTRO — OdooBuilding
**Proyecto:** building_dashboard (Odoo 19 CE)  
**Developer:** Mois — NextPack, Zapopan Jalisco MX  
**Fecha:** 2026-03-02 *(actualizado con análisis competitivo OPUS M2)*  

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

| Etapa | Nombre | vs OPUS M2 |
|---|---|---|
| 0 | Bootstrap / Base (building.work, menús, catálogos) | 🟢 Sin equivalente |
| 1 | Presupuesto estructurado (partidas, importes, anticipos) | 🟢 Igual |
| 2 | Planeación de Etapas/Fases con fechas y semáforos | 🟡 Parcial — falta semáforo por monto/contrato |
| 3.1 | Dashboard + KPIs + Alertas automáticas | 🟢 Mejor — OPUS no tiene dashboard financiero nativo |
| 3.2 | Avance físico por etapas | 🟡 Parcial — OPUS lo hace por partida individual con bloqueo |
| 3.3 | Semáforos + Drilldowns + Normalización | 🟢 Igual |
| 4.1 | Gastos Adicionales / Costos Operativos | 🟢 Igual |
| 4.2 | Evidencias de Obra (fotos/documentos) | 🟡 Parcial — OPUS las vincula a partida específica |
| 4.3a | Presupuestos Múltiples (base + extras/adendas) | 🟢 Igual |
| 4.3b | Wizard de Consolidación (merge automático) | 🟢 Mejor — OPUS no tiene merge automático |
| 4.4a | Distribución de Facturas → Obras | 🟢 Igual |
| 4.4b | Contabilidad Analítica por Obra | 🟢 Mejor — OPUS depende de enlace externo ERP |
| 4.4c | Carga CFDI XML (validación SAT 4.0) | 🏆 Exclusivo OdooBuilding |
| 4.6 | Identificador Obra Pública / Contrato | 🏆 Exclusivo OdooBuilding |
| 4.7 | Reporte Paramétrico Financiero (vista + Excel) | 🟢 Igual |
| 5.1 | Asistente IA Chat Conversacional (Claude/Gemini/GPT) | 🏆 Exclusivo OdooBuilding |
| Fix 5.1b | _create_work_from_json() defensivo — 5 bugs corregidos | — |
| Fix 5.1c | UI: botones redundantes eliminados, tab Claude habilitado | — |

### 🔄 FIXES EN CURSO (5.1)

| Fix | Descripción | Estado |
|---|---|---|
| F1 | Chat UI layout vertical (tipo WhatsApp) | ✅ Completado |
| F2 | Calidad del presupuesto IA (más capítulos/partidas) | ✅ Completado |
| F3 | Etapas filtradas por obra en kanban | ✅ Completado |

---

### 🟡 MEJORAS A ETAPAS TERMINADAS (parciales vs OPUS)

> Etapas ya existentes que necesitan subetapas para alcanzar nivel OPUS.

#### Etapa 3.2-M — Avance Físico por Partida *(Mejora a 3.2)*
**Prerequisito de:** 5.8 Monitor de Rendimientos y 5.9 Control Volúmenes

| Subetapa | Nombre | Descripción |
|---|---|---|
| 3.2-Ma | Avance físico por partida individual | Desglosar % avance hasta nivel `building.budget.line`, no solo por etapa |
| 3.2-Mb | Bloqueo de partida al llegar al 100% | Impedir más avance sin autorización explícita |
| 3.2-Mc | Historial de avance por partida | Registro período a período por partida (base para Sábana de Estimaciones) |

#### Etapa 2-M — Semáforos por Contrato *(Mejora a Etapa 2)*

| Subetapa | Nombre | Descripción |
|---|---|---|
| 2-Ma | Semáforo por monto comprometido vs contrato | Alerta cuando el gasto acumulado se acerca al techo del contrato |
| 2-Mb | Semáforo de estado de autorización | Indicador visual si la etapa tiene documentos pendientes de autorizar |

#### Etapa 4.2-M — Evidencias Vinculadas a Partida *(Mejora a Etapa 4.2)*

| Subetapa | Nombre | Descripción |
|---|---|---|
| 4.2-Ma | Vincular evidencia a `building.budget.line` | Cada foto/doc se asocia a una partida concreta, no solo a la obra |
| 4.2-Mb | Visor de evidencias en vista de avance | Al registrar avance de una partida, se adjuntan y ven sus evidencias directamente |

---

### ⏳ PENDIENTES — ROADMAP ORIGINAL (con subetapas OPUS)

#### Etapa 4.5 — Jornales / Mano de Obra
**Prioridad:** Pospuesta | **vs OPUS:** 🔴 Muy por debajo

| Subetapa | Nombre | Descripción |
|---|---|---|
| 4.5a | Registro básico de jornales (días/trabajador) | Base mínima original |
| 4.5b | Contratos tipo Destajo (mano de obra pura) | OPUS separa materiales de mano de obra contratada |
| 4.5c | Recursos Perseguidos por Destajo | Materiales que la empresa debe suministrar a la cuadrilla |
| 4.5d | Requisiciones automáticas desde contrato Destajo | Genera OC de materiales al "fincar" un destajo |

#### Etapa 5.2 — Flujo de Aprobación de Gastos
**Prioridad:** 🔴 Alta | **vs OPUS:** 🟡 Parcial

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.2a | Flujo básico: borrador → aprobado → rechazado | Lo planeado originalmente |
| 5.2b | Jerarquía por rol de obra | Residente → Superintendente → Gerente → Finanzas |
| 5.2c | Aprobación por umbral de monto configurable | Flujo diferente según importe del gasto |

#### Etapa 5.3 — Fechas y Alertas por Etapa
**Prioridad:** Media | **vs OPUS:** 🟡 Parcial

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.3a | Fechas inicio/fin con alertas básicas | Lo planeado originalmente |
| 5.3b | Alertas de vencimiento vinculadas a contrato | Alerta cuando una etapa excede la fecha del contrato vigente |

#### Etapa 5.4 — Vista Resumen Granular por Fase/Concepto
**Prioridad:** Media | **vs OPUS:** 🟡 Parcial

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.4a | Vista resumen agrupado por etapa/capítulo | Lo planeado originalmente |
| 5.4b | Sábana de Estimaciones horizontal | Historial de avances período a período en vista tabular cruzada (requiere 3.2-Mc) |

#### Etapa 5.5 — Perfiles y Permisos (Roles)
**Prioridad:** Baja | **vs OPUS:** 🟡 Parcial

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.5a | Grupos básicos: admin, residente, director | Lo planeado originalmente |
| 5.5b | Permisos por tipo de documento y monto | Restringe quién autoriza: gasto, estimación, contrato |

---

### 🆕 ETAPAS NUEVAS — DETECTADAS DEL ANÁLISIS OPUS M2

#### Etapa 5.6 — Órdenes de Cambio (Aditivas / Deductivas)
**vs OPUS:** 🔴 No existe | **Impacto:** 🔴 Alto
> OPUS modifica contratos en curso manteniendo presupuesto base intacto con trazabilidad completa.

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.6a | Modelo `building.change.order` | Entidad: tipo (aditiva/deductiva), monto, justificación |
| 5.6b | Flujo de autorización de cambio | Estados: borrador → solicitado → autorizado → aplicado |
| 5.6c | Afectación al presupuesto sin tocar baseline | Cambio se registra como adenda; presupuesto base intacto |
| 5.6d | Trazabilidad histórica de cambios | Línea de tiempo: qué cambió, cuándo, quién autorizó |

#### Etapa 5.7 — Escenario de Ejecución vs Oferta
**vs OPUS:** 🔴 No existe | **Impacto:** 🔴 Alto
> OPUS separa "lo que cobras al cliente" (Oferta) de "lo que te cuesta construir" (Ejecución).

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.7a | `budget_type = 'ejecucion'` en `building.budget` | Segundo presupuesto interno de costo directo |
| 5.7b | Vista comparativa Oferta vs Ejecución | Panel lado a lado: precio venta vs costo real proyectado |
| 5.7c | Ajuste de rendimientos en presupuesto ejecución | Residente optimiza % desperdicio sin tocar precio de venta |
| 5.7d | KPI Margen Bruto proyectado en Dashboard | Oferta − Ejecución = utilidad proyectada en tiempo real |

#### Etapa 5.8 — Monitor de Rendimientos (APU Teórico vs Real)
**vs OPUS:** 🔴 No existe | **Impacto:** 🔴 Alto
> OPUS compara insumos que *debieron* consumirse (según avance) vs lo que *realmente* salió de almacén.
> **Prerequisito:** 3.2-Mc (historial de avance por partida)

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.8a | Modelo de Análisis de Precio Unitario (APU) | Matriz: concepto → insumos → cantidades → rendimiento teórico |
| 5.8b | Explosión teórica de insumos por avance | 30% avance en cimentación → calcula acero/cemento teórico |
| 5.8c | Comparativa teórico vs real (cruce con `stock.move`) | Detecta desviaciones entre teoría y salidas reales de almacén |
| 5.8d | Semáforo de desviación de rendimiento | Verde ≤5% / Amarillo 5–15% / Rojo >15% de desvío |

#### Etapa 5.9 — Control de Volúmenes Extraordinarios
**vs OPUS:** 🔴 No existe | **Impacto:** 🟡 Medio
> **Prerequisito:** 3.2-Mb (bloqueo de partida al 100%)

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.9a | Bloqueo automático al 100% de volumen | No permite registrar más avance del presupuestado sin autorización |
| 5.9b | Tipo de volumen: Ordinario vs Extraordinario | Campo en `building.real.line` para distinguir origen del cobro |
| 5.9c | Validación automática contra presupuesto base | Warning o bloqueo si gasto real supera monto presupuestado de la partida |

#### Etapa 5.10 — Portal del Residente (Trazabilidad Logística)
**vs OPUS:** 🔴 No existe | **Impacto:** 🟡 Medio — Ventaja potencial OdooBuilding
> OdooBuilding vive dentro del ERP. Esta etapa explota esa ventaja nativa.

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.10a | Vista de requisiciones por obra | El residente ve sus solicitudes de compra y su estado actual |
| 5.10b | Semáforo logístico completo | Solicitado → cotización → comprado → pagado → en almacén |
| 5.10c | Notificación al residente al recibir material | Alerta automática cuando el material llega al almacén de la obra |

#### Etapa 5.11 — Biblioteca de Partidas y Plantillas WBS
**vs OPUS:** 🔴 No existe | **Impacto:** 🟡 Medio

| Subetapa | Nombre | Descripción |
|---|---|---|
| 5.11a | Modelos `building.template.chapter` / `building.template.line` | Biblioteca central de capítulos y partidas tipo |
| 5.11b | Wizard de importación de plantilla a presupuesto | Selector: elige capítulos/partidas de la biblioteca e importa a la obra activa |
| 5.11c | Rendimientos históricos por partida | Cada partida guarda rendimiento real de las últimas N obras donde se usó |

---

### 🏆 EXCLUSIVOS OdooBuilding — Sin equivalente en OPUS

| Funcionalidad | Estado |
|---|---|
| 🇲🇽 Carga CFDI XML + validación SAT 4.0 | ✅ Único en el mercado |
| 🤖 Asistente IA conversacional (Claude/Gemini/GPT) | ✅ Único en el mercado |
| 📊 Contabilidad analítica nativa sin enlace externo | ✅ Ventaja estructural |
| 🏗️ Identificador Obra Pública/Privada con reglas fiscales MX | ✅ Único mercado MX |
| 🔗 Integración ERP nativa (compras, almacén, finanzas) | ✅ Ventaja estructural |

---

### 📋 ORDEN DE EJECUCIÓN RECOMENDADO

| # | Etapa | Tipo | Razón |
|---|---|---|---|
| 1 | Fix F2 / F3 (5.1) | Fix | Terminar lo que está en curso |
| 2 | **3.2-Ma → 3.2-Mc** | Mejora | Prerequisito de 5.8 y 5.9 |
| 3 | **5.2a → 5.2c** | Pendiente | Alta prioridad comprometida |
| 4 | **5.6a → 5.6d** | Nueva | Brecha crítica: trazabilidad de cambios |
| 5 | **5.7a → 5.7d** | Nueva | Brecha crítica: control de márgenes |
| 6 | **5.3 / 5.4** | Pendiente | Alertas y Sábana de Estimaciones |
| 7 | **5.9a → 5.9c** | Nueva | Bloqueo volúmenes (requiere 3.2-Mb) |
| 8 | **5.8a → 5.8d** | Nueva | Monitor APU (requiere 3.2-Mc) |
| 9 | **5.5a → 5.5b** | Pendiente | Perfiles y permisos |
| 10 | **4.5a → 4.5d** | Pendiente | Jornales completos con destajo |
| 11 | **2-Ma → 2-Mb** | Mejora | Semáforos por contrato |
| 12 | **4.2-Ma → 4.2-Mb** | Mejora | Evidencias vinculadas a partida |
| 13 | **5.10 / 5.11** | Nueva | Portal residente + Biblioteca partidas |

---

## MODELOS PRINCIPALES

```
building.work              — Obra principal
building.budget            — Presupuesto (base/extra/consolidado/ejecucion)
building.budget.chapter    — Capítulo del presupuesto
building.budget.line       — Partida (code, name, amount, period_from int, period_to int)
building.work.stage        — Etapa/Fase (state: planning/in_progress/to_approve/done)
building.real.line         — Gasto real (+ tipo_volumen: ordinario/extraordinario en 5.9)
building.work.cost         — Costo adicional/indirecto
building.work.evidence     — Evidencia fotográfica (+ budget_line_id en 4.2-Ma)
building.bill.allocation   — Distribución de factura a obra
building.ai.chat           — Chat IA (state: draft/generated)
building.ai.chat.message   — Mensaje del chat (role: user/assistant)
building.ai.config         — Configuración de API keys IA
building.ai.config.wizard  — Wizard configuración (claude_model, gemini_model, openai_model)
--- NUEVOS (pendientes de implementar) ---
building.change.order      — Orden de Cambio Aditiva/Deductiva (Etapa 5.6)
building.apu               — Análisis de Precio Unitario — matriz insumos/rendimientos (Etapa 5.8)
building.apu.line          — Línea de insumo del APU (Etapa 5.8)
building.template.chapter  — Capítulo de plantilla WBS (Etapa 5.11)
building.template.line     — Partida de plantilla WBS (Etapa 5.11)
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

1. ✅ Confirmar Fix F1 (chat UI vertical) en Antigravity
2. ✅ Fix F2 — Calidad del presupuesto IA completado
3. ✅ Fix F3 — Etapas filtradas por obra en kanban completado
4. ✅ Análisis competitivo OPUS M2 completado — roadmap reordenado
5. ⏳ Arrancar Etapa 3.2-Ma — Avance físico por partida (prerequisito de 5.8 y 5.9)
6. ⏳ Arrancar Etapa 5.2a — Flujo aprobación de gastos
