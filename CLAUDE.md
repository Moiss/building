# CLAUDE.md — Proyecto OdooBuilding (módulo: building_dashboard)

> **Fuente única de verdad** para que Claude Code entienda el proyecto,
> lo ya implementado, la arquitectura y lo que sigue.
>
> Lee también: `contexto_maestro_odoobuilding.md` para el roadmap completo,
> análisis competitivo vs OPUS M2 y estado detallado de cada etapa.

---

## 1. Qué es OdooBuilding

Vertical de **Odoo 19 Community Edition** para **control de obras de construcción en México**.
El módulo principal se llama `building_dashboard`.

El core actual cubre:

- Alta de Obras
- Presupuestos y Partidas
- Planeación por Etapas/Fases
- Control de Avance Físico con semáforos, dashboard, alertas y drilldowns
- Gastos Adicionales / Costos Operativos
- Evidencias de Obra (fotos/documentos)
- Presupuestos Múltiples + Wizard de Consolidación
- Distribución de Facturas a Obras
- Contabilidad Analítica por Obra
- Carga CFDI XML (validación SAT 4.0)
- Identificador Obra Pública / Contrato
- Reporte Paramétrico Financiero (vista + Excel)
- Asistente IA Chat Conversacional (Claude / Gemini / GPT)

---

## 2. Stack Técnico y Reglas del Proyecto

- **Odoo 19 Community Edition** (NO Enterprise)
- **Python 3** (modelos, lógica, wizards)
- **XML** (vistas, menús, acciones, seguridad)
- **MariaDB** (base de datos Odoo)
- **Base de datos:** `building_dashboard`
- **Ruta local:** `/Users/macbookpro/odoo/odoo19ce/proyectos/building_dashboard`
- En Odoo 19 las vistas de lista usan `<list>` (NO `<tree>`)
- Sin `attrs=""` deprecated
- Sin `expand="1"`
- El desarrollador es principiante en Odoo/Python:
  - Siempre incluir comentarios explicativos en el codigo
  - Explicar que hace cada funcion/metodo
  - Comentar las relaciones entre modelos

### Politica de entregables por etapa

Cada etapa debe incluir:

1. **Walkthrough** (paso a paso de uso)
2. **Implementation plan** (plan de implementacion)
3. **Tasks** (checklist de tareas)
4. **QA** (pruebas obligatorias)

Todo en **ESPANOL**.

### Palabra clave para prompts avanzados

`MODO FACTURAR`

---

## 3. Arquitectura: Motor de Calculo (Engine)

### Principio clave

Existe un **motor/engine** que centraliza los calculos de rollups para dashboards:

- Totales y porcentajes agregados
- Drilldowns
- Semaforos

### Reglas del motor

1. Los "show fields" (campos visibles en Obra/Etapa) usan `compute` + `store=True` para performance
2. La logica de rollup se centraliza en el motor, NO se duplica en multiples modelos
3. Los modelos transaccionales solo calculan lo basico del registro individual
4. El motor usa `read_group` para performance en agregados
5. CRITICO: Motor de costos es distinto al Motor de avance (3.x), son modulos logicos SEPARADOS

### Ejemplo aplicado (Etapa 4.1 Costos)

- `building.work.cost` calcula `amount = qty * unit_cost` (nivel registro)
- El motor calcula `executed_*` por obra usando `read_group` (nivel agregado)

---

## 4. Reglas Funcionales (NO olvidar)

1. Avance fisico NO es igual a Costos
   - Avance fisico (Etapa 3.x): porcentajes y semaforos de progreso
   - Costos (Etapa 4.1): ejecutado presupuestado/adicional, desviacion
2. Los "adicionales" pueden ocurrir en cualquier etapa pero NO incrementan avance fisico
3. La UI debe ser rapida: agregados por motor con read_group + campos store
4. QA siempre obligatorio por etapa
5. Evitar que cambios rompan menus o dupliquen vistas (problema historico del proyecto)
6. Nunca modificar modelos nativos Odoo, siempre extender con `_inherit`

---

## 5. Modelos Core (existentes)

### Modelos activos

```
building.work              -- Obra principal
building.budget            -- Presupuesto (base/extra/consolidado)
building.budget.chapter    -- Capitulo del presupuesto
building.budget.line       -- Partida (code, name, amount, period_from int, period_to int)
building.work.stage        -- Etapa/Fase (state: planning/in_progress/to_approve/done)
building.real.line         -- Gasto real
building.work.cost         -- Costo adicional/indirecto
building.work.evidence     -- Evidencia fotografica
building.bill.allocation   -- Distribucion de factura a obra
building.ai.chat           -- Chat IA (state: draft/generated)
building.ai.chat.message   -- Mensaje del chat (role: user/assistant)
building.ai.config         -- Configuracion de API keys IA
building.ai.config.wizard  -- Wizard configuracion (claude_model, gemini_model, openai_model)
```

### Modelos nuevos (pendientes de implementar)

```
building.change.order      -- Orden de Cambio Aditiva/Deductiva (Etapa 5.6)
building.apu               -- Analisis de Precio Unitario (Etapa 5.8)
building.apu.line          -- Linea de insumo del APU (Etapa 5.8)
building.template.chapter  -- Capitulo de plantilla WBS (Etapa 5.11)
building.template.line     -- Partida de plantilla WBS (Etapa 5.11)
```

### Campos criticos verificados

- `building.budget.line`: NO tiene unit_id, quantity, unit_price. period_from/to son Integer
- `building.work.stage`: state valido = 'planning' (NO 'planned'). NO tiene percent_weight
- `building.ai.config.wizard`: usa claude_status (no claude_state) y claude_last4 (no claude_key_last4)

---

## 6. Roadmap Completo

### TERMINADAS

| Etapa | Nombre | vs OPUS M2 |
|---|---|---|
| 0 | Bootstrap / Base | Sin equivalente |
| 1 | Presupuesto estructurado | Igual |
| 2 | Planeacion de Etapas/Fases con fechas y semaforos | Parcial - falta semaforo por monto/contrato |
| 3.1 | Dashboard + KPIs + Alertas automaticas | Mejor - OPUS no tiene dashboard financiero nativo |
| 3.2 | Avance fisico por etapas | Parcial - OPUS lo hace por partida individual con bloqueo |
| 3.3 | Semaforos + Drilldowns + Normalizacion | Igual |
| 4.1 | Gastos Adicionales / Costos Operativos | Igual |
| 4.2 | Evidencias de Obra (fotos/documentos) | Parcial - OPUS las vincula a partida especifica |
| 4.3a | Presupuestos Multiples (base + extras/adendas) | Igual |
| 4.3b | Wizard de Consolidacion (merge automatico) | Mejor - OPUS no tiene merge automatico |
| 4.4a | Distribucion de Facturas a Obras | Igual |
| 4.4b | Contabilidad Analitica por Obra | Mejor - OPUS depende de enlace externo ERP |
| 4.4c | Carga CFDI XML (validacion SAT 4.0) | EXCLUSIVO OdooBuilding |
| 4.6 | Identificador Obra Publica / Contrato | EXCLUSIVO OdooBuilding |
| 4.7 | Reporte Parametrico Financiero (vista + Excel) | Igual |
| 5.1 | Asistente IA Chat Conversacional (Claude/Gemini/GPT) | EXCLUSIVO OdooBuilding |
| Fix 5.1b | _create_work_from_json() defensivo - 5 bugs corregidos | -- |
| Fix 5.1c | UI: botones redundantes eliminados, tab Claude habilitado | -- |
| Fix F1 | Chat UI layout vertical (tipo WhatsApp) | COMPLETADO |
| Fix F2 | Calidad del presupuesto IA (mas capitulos/partidas) | COMPLETADO |
| Fix F3 | Etapas filtradas por obra en kanban | COMPLETADO |

---

### MEJORAS A ETAPAS TERMINADAS (parciales vs OPUS)

#### Etapa 3.2-M - Avance Fisico por Partida (Mejora a 3.2)
Prerequisito de: Etapa 5.8 y Etapa 5.9

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 3.2-Ma | Avance fisico por partida individual | Desglosar porcentaje de avance hasta nivel building.budget.line |
| 3.2-Mb | Bloqueo de partida al llegar al 100% | Impedir mas avance sin autorizacion explicita |
| 3.2-Mc | Historial de avance por partida | Registro periodo a periodo por partida (base para Sabana de Estimaciones) |

#### Etapa 2-M - Semaforos por Contrato (Mejora a Etapa 2)

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 2-Ma | Semaforo por monto comprometido vs contrato | Alerta cuando el gasto acumulado se acerca al techo del contrato |
| 2-Mb | Semaforo de estado de autorizacion | Indicador visual si la etapa tiene documentos pendientes de autorizar |

#### Etapa 4.2-M - Evidencias Vinculadas a Partida (Mejora a Etapa 4.2)

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 4.2-Ma | Vincular evidencia a building.budget.line | Cada foto/doc se asocia a una partida concreta, no solo a la obra |
| 4.2-Mb | Visor de evidencias en vista de avance | Al registrar avance de una partida se adjuntan y ven sus evidencias directamente |

---

### PENDIENTES - ROADMAP ORIGINAL (con subetapas OPUS)

#### Etapa 4.5 - Jornales / Mano de Obra
Prioridad: Pospuesta | vs OPUS: Muy por debajo

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 4.5a | Registro basico de jornales (dias/trabajador) | Base minima original |
| 4.5b | Contratos tipo Destajo (mano de obra pura) | OPUS separa materiales de mano de obra contratada |
| 4.5c | Recursos Perseguidos por Destajo | Materiales que la empresa debe suministrar a la cuadrilla |
| 4.5d | Requisiciones automaticas desde contrato Destajo | Genera OC de materiales al fincar un destajo |

#### Etapa 5.2 - Flujo de Aprobacion de Gastos
Prioridad: ALTA | vs OPUS: Parcial

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.2a | Flujo basico: borrador - aprobado - rechazado | Lo planeado originalmente |
| 5.2b | Jerarquia por rol de obra | Residente - Superintendente - Gerente - Finanzas |
| 5.2c | Aprobacion por umbral de monto configurable | Flujo diferente segun importe del gasto |

#### Etapa 5.3 - Fechas y Alertas por Etapa
Prioridad: Media | vs OPUS: Parcial

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.3a | Fechas inicio/fin con alertas basicas | Lo planeado originalmente |
| 5.3b | Alertas de vencimiento vinculadas a contrato | Alerta cuando una etapa excede la fecha del contrato vigente |

#### Etapa 5.4 - Vista Resumen Granular por Fase/Concepto
Prioridad: Media | vs OPUS: Parcial

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.4a | Vista resumen agrupado por etapa/capitulo | Lo planeado originalmente |
| 5.4b | Sabana de Estimaciones horizontal | Historial de avances periodo a periodo en vista tabular cruzada (requiere 3.2-Mc) |

#### Etapa 5.5 - Perfiles y Permisos (Roles)
Prioridad: Baja | vs OPUS: Parcial

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.5a | Grupos basicos: admin, residente, director | Lo planeado originalmente |
| 5.5b | Permisos por tipo de documento y monto | Restringe quien autoriza: gasto, estimacion, contrato |

---

### ETAPAS NUEVAS - DETECTADAS DEL ANALISIS OPUS M2

#### Etapa 5.6 - Ordenes de Cambio (Aditivas / Deductivas)
vs OPUS: No existe | Impacto: ALTO
OPUS modifica contratos en curso manteniendo presupuesto base intacto con trazabilidad completa.

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.6a | Modelo building.change.order | Entidad: tipo (aditiva/deductiva), monto, justificacion |
| 5.6b | Flujo de autorizacion de cambio | Estados: borrador - solicitado - autorizado - aplicado |
| 5.6c | Afectacion al presupuesto sin tocar baseline | Cambio se registra como adenda; presupuesto base intacto |
| 5.6d | Trazabilidad historica de cambios | Linea de tiempo: que cambio, cuando, quien autorizo |

#### Etapa 5.7 - Escenario de Ejecucion vs Oferta
vs OPUS: No existe | Impacto: ALTO
OPUS separa "lo que cobras al cliente" (Oferta) de "lo que te cuesta construir" (Ejecucion).

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.7a | budget_type = 'ejecucion' en building.budget | Segundo presupuesto interno de costo directo |
| 5.7b | Vista comparativa Oferta vs Ejecucion | Panel lado a lado: precio venta vs costo real proyectado |
| 5.7c | Ajuste de rendimientos en presupuesto ejecucion | Residente optimiza porcentaje de desperdicio sin tocar precio de venta |
| 5.7d | KPI Margen Bruto proyectado en Dashboard | Oferta menos Ejecucion = utilidad proyectada en tiempo real |

#### Etapa 5.8 - Monitor de Rendimientos (APU Teorico vs Real)
vs OPUS: No existe | Impacto: ALTO
Prerequisito: 3.2-Mc (historial de avance por partida)

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.8a | Modelo de Analisis de Precio Unitario (APU) | Matriz: concepto - insumos - cantidades - rendimiento teorico |
| 5.8b | Explosion teorica de insumos por avance | 30% avance en cimentacion calcula acero/cemento teorico |
| 5.8c | Comparativa teorico vs real (cruce con stock.move) | Detecta desviaciones entre teoria y salidas reales de almacen |
| 5.8d | Semaforo de desviacion de rendimiento | Verde menor 5% / Amarillo 5-15% / Rojo mayor 15% de desvio |

#### Etapa 5.9 - Control de Volumenes Extraordinarios
vs OPUS: No existe | Impacto: MEDIO
Prerequisito: 3.2-Mb (bloqueo de partida al 100%)

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.9a | Bloqueo automatico al 100% de volumen | No permite registrar mas avance del presupuestado sin autorizacion |
| 5.9b | Tipo de volumen: Ordinario vs Extraordinario | Campo en building.real.line para distinguir origen del cobro |
| 5.9c | Validacion automatica contra presupuesto base | Warning o bloqueo si gasto real supera monto presupuestado de la partida |

#### Etapa 5.10 - Portal del Residente (Trazabilidad Logistica)
vs OPUS: No existe | Impacto: MEDIO - Ventaja potencial OdooBuilding
OdooBuilding vive dentro del ERP. Esta etapa explota esa ventaja nativa.

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.10a | Vista de requisiciones por obra | El residente ve sus solicitudes de compra y su estado actual |
| 5.10b | Semaforo logistico completo | Solicitado - cotizacion - comprado - pagado - en almacen |
| 5.10c | Notificacion al residente al recibir material | Alerta automatica cuando el material llega al almacen de la obra |

#### Etapa 5.11 - Biblioteca de Partidas y Plantillas WBS
vs OPUS: No existe | Impacto: MEDIO

| Subetapa | Nombre | Descripcion |
|---|---|---|
| 5.11a | Modelos building.template.chapter y building.template.line | Biblioteca central de capitulos y partidas tipo |
| 5.11b | Wizard de importacion de plantilla a presupuesto | Selector: elige capitulos/partidas de la biblioteca e importa a la obra activa |
| 5.11c | Rendimientos historicos por partida | Cada partida guarda rendimiento real de las ultimas N obras donde se uso |

---

### EXCLUSIVOS OdooBuilding - Sin equivalente en OPUS

| Funcionalidad | Estado |
|---|---|
| Carga CFDI XML + validacion SAT 4.0 | UNICO en el mercado |
| Asistente IA conversacional (Claude/Gemini/GPT) | UNICO en el mercado |
| Contabilidad analitica nativa sin enlace externo | Ventaja estructural |
| Identificador Obra Publica/Privada con reglas fiscales MX | Unico mercado MX |
| Integracion ERP nativa (compras, almacen, finanzas) | Ventaja estructural |

---

### ORDEN DE EJECUCION RECOMENDADO

| Num | Etapa | Tipo | Razon |
|---|---|---|---|
| 1 | Fix F2 y F3 (5.1) | Fix | Ya completados |
| 2 | 3.2-Ma a 3.2-Mc | Mejora | Prerequisito de 5.8 y 5.9 |
| 3 | 5.2a a 5.2c | Pendiente | Alta prioridad comprometida |
| 4 | 5.6a a 5.6d | Nueva | Brecha critica: trazabilidad de cambios |
| 5 | 5.7a a 5.7d | Nueva | Brecha critica: control de margenes |
| 6 | 5.3 y 5.4 | Pendiente | Alertas y Sabana de Estimaciones |
| 7 | 5.9a a 5.9c | Nueva | Bloqueo volumenes (requiere 3.2-Mb) |
| 8 | 5.8a a 5.8d | Nueva | Monitor APU (requiere 3.2-Mc) |
| 9 | 5.5a y 5.5b | Pendiente | Perfiles y permisos |
| 10 | 4.5a a 4.5d | Pendiente | Jornales completos con destajo |
| 11 | 2-Ma y 2-Mb | Mejora | Semaforos por contrato |
| 12 | 4.2-Ma y 4.2-Mb | Mejora | Evidencias vinculadas a partida |
| 13 | 5.10 y 5.11 | Nueva | Portal residente + Biblioteca partidas |

---

## 7. Comportamiento del Asistente IA (building_ai_chat.py)

### Flujo conversacional (system prompt 5 turnos)

1. Turno 1: Pregunta tipo de obra
2. Turno 2: Superficie y municipio
3. Turno 3: Niveles, distribucion, acabados
4. Turno 4: Resumen textual con desglose + confirmacion
5. Turno 5: Solo si confirma - genera JSON - crea obra

### _create_work_from_json() - campos permitidos

```python
building.work:           name, company_id
building.budget:         work_id, name, budget_type='base'
building.budget.chapter: budget_id, code, name, sequence
building.budget.line:    chapter_id, code, name, amount, sequence, period_from(int), period_to(int)
building.work.stage:     work_id, name, sequence, state='planning'
```

### Modelos de IA configurados

Claude (Anthropic):
- claude-opus-4-6
- claude-opus-4-5-20251101
- claude-sonnet-4-6 (default)
- claude-sonnet-4-5-20250929
- claude-haiku-4-5-20251001

Gemini (Google):
- gemini-3-pro-preview
- gemini-3-flash-preview (default)
- gemini-2.5-pro
- gemini-2.5-flash
- gemini-2.5-flash-lite

OpenAI:
- gpt-5.2
- gpt-5.2-pro
- gpt-5.2-chat-latest (default)
- gpt-5-mini

---

## 8. Problemas Historicos (evitar repetir)

1. Menus rotos: prompts que desmadraron menus/acciones en base nueva
2. Dashboard no refrescaba: al cerrar wizard de avance hasta dar F5
3. Progressbars desincronizadas: porcentajes no se reflejaban en ciertas etapas/partidas
4. Borrado indebido: en ciertos estados no debe permitir borrados (ocultar boton eliminar segun estado)
5. Vistas duplicadas: al regenerar XML sin verificar IDs existentes

---

## 9. Dev Workflow

- Se trabaja por etapas y sub-etapas
- Cada etapa se implementa con un prompt que incluye: walkthrough + plan + tasks + QA
- GIT: branch por etapa (etapa-5.2, etapa-5.6, etc.) para rollback facil
- SIN git push hasta orden explicita de Mois
- Evitar que prompts rompan menus o dupliquen vistas
- El codigo generado por IA debe ser revisado y probado antes de merge
- Antigravity workflow: primero prompt de diagnostico (solo lectura), luego prompt de fix certero

### Upgrade command

```bash
python odoo-bin \
  -c /Users/macbookpro/odoo/odoo19ce/proyectos/building_dashboard/odoo.conf \
  -d building_dashboard \
  -u building_dashboard
```

---

## 10. Convenciones de Codigo

```python
# Siempre:
# - Comentar cada clase explicando su proposito
# - Comentar cada metodo explicando que hace
# - Comentar campos no obvios
# - Usar docstrings en espanol
# - Seguir naming conventions de Odoo (building.work.xxx)
# - Usar _name, _description, _order en cada modelo

# Ejemplo de estilo esperado:
class BuildingWorkCost(models.Model):
    """
    Modelo para registrar costos operativos de obra.
    Incluye costos presupuestados y adicionales.
    NO afecta el avance fisico de la obra.
    """
    _name = 'building.work.cost'
    _description = 'Costo Operativo de Obra'
    _order = 'date desc, id desc'

    # --- Relaciones ---
    work_id = fields.Many2one(
        'building.work',
        string='Obra',
        required=True,
        ondelete='cascade',
        help='Obra a la que pertenece este costo',
    )
```

---

## 11. Estructura esperada del modulo

```
building_dashboard/
|-- __init__.py
|-- __manifest__.py
|-- CLAUDE.md                              <- Este archivo (Claude Code / Antigravity)
|-- contexto_maestro_odoobuilding.md       <- Roadmap completo + analisis OPUS M2
|-- models/
|   |-- __init__.py
|   |-- building_work.py                   # Modelo principal de Obra
|   |-- building_work_stage.py             # Etapas/Fases
|   |-- building_budget.py                 # Presupuesto (base/extra/consolidado/ejecucion)
|   |-- building_budget_line.py            # Partidas de presupuesto
|   |-- building_work_cost.py              # OK 4.1 Costos operativos
|   |-- building_work_evidence.py          # OK 4.2 Evidencias
|   |-- building_work_jornal.py            # PENDIENTE 4.5 Jornales
|   |-- building_bill_allocation.py        # OK 4.4a Distribucion facturas
|   |-- building_ai_chat.py                # OK 5.1 Asistente IA
|   |-- building_change_order.py           # NUEVO 5.6 Ordenes de Cambio
|   |-- building_apu.py                    # NUEVO 5.8 APU Analisis Precio Unitario
|   |-- building_template.py               # NUEVO 5.11 Biblioteca Plantillas WBS
|   +-- engine/
|       |-- __init__.py
|       |-- progress_engine.py             # OK Motor de avance fisico (3.x)
|       +-- cost_engine.py                 # OK Motor de costos (4.1)
|-- views/
|   |-- building_work_views.xml
|   |-- building_stage_views.xml
|   |-- building_budget_views.xml
|   |-- building_cost_views.xml            # OK 4.1
|   |-- building_evidence_views.xml        # OK 4.2
|   |-- building_ai_chat_views.xml         # OK 5.1
|   |-- building_change_order_views.xml    # NUEVO 5.6
|   |-- building_apu_views.xml             # NUEVO 5.8
|   +-- menu.xml
|-- security/
|   |-- ir.model.access.csv
|   +-- security.xml
|-- wizards/
|-- data/
+-- static/
    +-- src/
        +-- components/
            +-- chat_messages/             # OK BuildingChatMessages OWL component
```

---

## 12. Instrucciones para Claude Code

Al iniciar en este proyecto:

1. Lee este archivo primero: es tu contexto base
2. Lee `contexto_maestro_odoobuilding.md`: roadmap completo y analisis competitivo OPUS M2
3. Revisa `models/`: compara con lo documentado aqui y ajusta tu entendimiento
4. Revisa `views/`: identifica menus y vistas existentes para no duplicar
5. Revisa `security/`: identifica grupos y ACL existentes
6. Antes de crear archivos nuevos verifica que no existan ya
7. Antes de modificar menus/vistas revisa XML IDs existentes
8. Todo codigo nuevo debe seguir las convenciones de la seccion 10
9. Todo entregable debe incluir walkthrough + plan + tasks + QA en espanol
10. NUNCA git push hasta recibir orden explicita de Mois
