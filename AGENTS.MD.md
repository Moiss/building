---
trigger: always_on
---

# AGENTS.md — Proyecto OdooBuilding (módulo: building_dashboard)

El walkthrough,task e implementaton plan en español.

> **Fuente única de verdad** para que el agente de Antigravity entienda el proyecto,
> la arquitectura, lo ya implementado, las reglas funcionales y lo que sigue.
> LEER COMPLETO antes de modificar cualquier archivo.

---

## 1. ¿Qué es OdooBuilding?

Vertical de **Odoo 19 Community Edition** para **control de obras de construcción**.
El módulo principal se llama `building_dashboard`.

El sistema cubre:

- Alta de Obras con dashboard financiero y de avance
- Presupuestos estructurados por capítulos y partidas
- Planeación por Etapas/Frentes
- Control de Avance Físico con semáforos, alertas y drilldowns
- Gastos Adicionales (indirectos de campo)
- Motor de cálculo centralizado (Engine) para performance

**Repositorio**: https://github.com/Moiss/building (público)

---

## 2. Stack Técnico y Reglas OBLIGATORIAS

- **Odoo 19 Community Edition** (NO Enterprise)
- **Python 3.11** (modelos, lógica, wizards)
- **XML** (vistas, menús, acciones, seguridad)
- **PostgreSQL** (base de datos Odoo)

### Reglas de Odoo 19 (CRÍTICO — no romper)

- Vistas de lista: usar `<list>` (NO `<tree>`)
- Vistas search: NO usar `<group expand="1">`, los filtros de agrupación van directo dentro de `<search>`
- Atributos condicionales: usar `invisible="condicion"` directo (NO usar `attrs="{...}"` que está deprecado)
- Agregaciones: usar `_read_group()` (NO `read_group()` que está deprecado)
- API `_read_group` retorna tuplas: Many2one viene como record (.id), Selection/Char como valor directo

### Reglas de código

- **Siempre** incluir comentarios explicativos en el código
- **Siempre** explicar qué hace cada función/método con docstrings
- **Siempre** comentar las relaciones entre modelos
- **Siempre** docstrings y comentarios en **ESPAÑOL**
- Seguir naming conventions de Odoo: `building.work.xxx`

### Reglas de UI/UX

- Las pantallas deben verse **profesionales** con diseño moderno
- KPIs con íconos circulares, bordes limpios, colores con significado
- Recuadros informativos con bordes laterales de color
- Badges con fondo de color para estados/tipos
- Montos destacados en tamaño grande con fondo verde/rojo según contexto
- Usar Bootstrap 5 classes (row, col-\*, alert-info, etc.)
- Evitar formularios planos sin estructura visual

### Reglas de Git

- Branches por etapa: `etapa-4.1`, `etapa-4.2`, etc.
- NO hacer `git push` ni `git add` a menos que el usuario lo indique
- El checkout de rama solo se hace en el primer prompt de cada etapa

---

## 3. Arquitectura: Motor de Cálculo (Engine)

### Principio clave

Existe un **motor/engine** (`building.financial.engine` y `building.progress.engine`)
que centraliza los cálculos de rollups para dashboards.

### Reglas del motor

1. Los **"show fields"** (campos visibles en Obra/Etapa) → `compute` + `store=True` para performance
2. La **lógica de rollup se centraliza en el motor**, NO se duplica en múltiples modelos
3. Los modelos transaccionales solo calculan lo básico del registro individual
4. El motor usa **`_read_group`** (Odoo 19) para performance en agregados
5. **CRÍTICO**: Motor de costos ≠ Motor de avance (3.x) → son módulos lógicos **SEPARADOS**

### Cómo funciona

- `building.work.cost` calcula `amount = qty * unit_cost` (nivel registro)
- El **motor** (`financial_engine.get_cost_totals`) calcula `executed_*` por obra usando `_read_group` (nivel agregado)
- `building.work` tiene campos `compute` + `store=True` que llaman al motor
- CRUD de work.cost invalida cache → `_recompute_cost_totals()` en building.work

---

## 4. Reglas Funcionales (NO olvidar NUNCA)

1. **Avance físico ≠ Costos** — Son flujos completamente separados
2. **Gastos Adicionales** (clavos, silicón, resistol) pueden ocurrir en cualquier etapa pero **NO incrementan avance físico**
3. **Gastos Reales** (`building.real.line`) son otro flujo: vienen de CxP/facturas (Etapa 4.4 futura). NO confundir con Gastos Adicionales
4. La UI debe ser **rápida**: agregados por motor con `_read_group` + campos `store`
5. **QA siempre obligatorio** por etapa
6. Evitar que cambios **rompan menús** o **dupliquen vistas** (problema histórico del proyecto)
7. Al crear nuevos campos `store=True`, siempre ejecutar upgrade del módulo

---

## 5. Arquitectura de Gastos (IMPORTANTE)

Existen **2 flujos de gastos** en OdooBuilding. NUNCA mezclarlos:

### Gastos Reales (building.real.line) — Etapa 3.4, ya existe

- Gastos formales que en futuro vendrán de CxP/facturas (Etapa 4.4)
- Alimentan el KPI "Pagado" y los semáforos financieros
- Tienen número de factura, proveedor, prorrateo por obra
- **NO tocar desde prompts de Gastos Adicionales**

### Gastos Adicionales (building.work.cost) — Etapa 4.1, ya implementada

- Gastos indirectos del día a día: clavos, silicón, resistol, materiales menores
- Siempre son tipo "additional" (el campo cost_type se fuerza en create())
- Producto es **OBLIGATORIO** (catálogo compartido entre obras)
- Etapa es **OBLIGATORIA**
- Partida presupuestaria es **OPCIONAL**
- UdM existe en modelo pero es **invisible** en vistas
- Alimentan el KPI "Ejecutado Adicional" en el dashboard
- Acceso: SOLO desde smart button "Adicionales" en la Obra (NO hay menú suelto)

---

## 6. Modelos Core (lo que ya existe)

### `building.work` (Obra)

- Dashboard con KPIs: Presupuesto Total, Comprometido, Pagado, Disponible
- KPIs Ejecutado Operativo: Presupuestado, Adicional, Total
- Avance Físico Global + Avance Financiero con detección de desviación
- Smart buttons: Ver Presupuesto, Etapas, Solicitar Compra, Asistente IA, Gastos Reales, Adicionales
- Workflow: Borrador → Planeación → En Ejecución → Finalizada

### `building.work.stage` (Etapa/Frente)

- Relación a Obra
- Fechas planeadas y reales
- Avance físico con semáforos (engine)
- Semáforos financieros con drilldown

### `building.budget.line` (Partida de presupuesto)

- Obra + Etapa + Capítulo
- Monto presupuestado, ejecutado, avance
- Relaciones para drilldown

### `building.work.cost` (Gasto Adicional) — Etapa 4.1

- Tipo siempre "additional" (forzado en create)
- Producto obligatorio, Etapa obligatoria, Partida opcional
- amount = qty × unit_cost (compute, store)
- CRUD triggers recompute en building.work

### `building.real.line` (Gasto Real)

- Gastos formales/contables
- Relación a obra y partida
- Alimenta KPI "Pagado"

### `building.financial.engine` (Motor Financiero)

- get_cost_totals(work_ids) → totales de costos por obra
- get_real_amounts(budget_line_ids) → montos reales por partida
- get_stage_financial_totals(work_id) → totales por etapa
- get_traffic_light() → semáforos
- Todos usan `_read_group` (Odoo 19)

### `building.progress.engine` (Motor de Avance)

- Cálculos de avance físico (separado del financiero)

### Wizards

- Captura de avance por etapa/global
- Configuración IA
- Cargador de capítulos

---

## 7. Estructura Actual del Módulo

```
building_dashboard/
├── __init__.py
├── __manifest__.py
├── odoo.conf
├── AGENTS.md                           ← ESTE ARCHIVO
├── models/
│   ├── __init__.py
│   ├── building_work.py                # Obra principal + dashboard
│   ├── building_work_stage.py          # Etapas/Frentes
│   ├── building_budget.py              # Presupuesto
│   ├── building_budget_line.py         # Partidas
│   ├── building_budget_chapter.py      # Capítulos
│   ├── building_budget_period.py       # Periodos
│   ├── building_budget_progress.py     # Avance presupuestario
│   ├── building_stage_progress.py      # Avance por etapa
│   ├── building_real_line.py           # Gastos Reales (CxP futuro)
│   ├── building_work_alert.py          # Alertas
│   ├── building_ai_config.py           # Config IA
│   ├── work_cost.py                    # ✅ 4.1 Gastos Adicionales
│   ├── financial_engine.py             # Motor financiero (_read_group)
│   ├── progress_engine.py              # Motor de avance físico
│   ├── alert_engine.py                 # Motor de alertas
│   └── encryption_service.py           # Cifrado API Keys IA
├── views/
│   ├── building_work_views.xml         # Dashboard Obra + smart buttons
│   ├── building_stage_views.xml        # Etapas
│   ├── building_budget_views.xml       # Presupuesto + partidas
│   ├── building_alert_views.xml        # Alertas
│   ├── building_progress_views.xml     # Avance
│   ├── building_budget_progress_views.xml
│   ├── building_real_line_views.xml    # Gastos Reales
│   ├── work_cost_views.xml             # ✅ 4.1 Gastos Adicionales
│   ├── building_ai_config_wizard_views.xml
│   ├── building_change_real_source_wizard_views.xml
│   ├── building_chapter_loader_wizard_views.xml
│   └── menus.xml                       # Menús (sin Costos suelto)
├── security/
│   ├── security.xml                    # Grupos
│   ├── ir.model.access.csv            # ACL
│   └── ir_rule.xml                     # Record rules
├── wizard/
├── data/
└── static/
```

---

## 8. Roadmap Completo

### ✅ RELEASE V1 — Operación de Obra (sin contabilidad)

| Etapa | Nombre                                 | Estado       |
| ----- | -------------------------------------- | ------------ |
| 0     | Bootstrap / Base                       | ✅ TERMINADA |
| 1     | Presupuesto estructurado               | ✅ TERMINADA |
| 2     | Planeación de Etapas/Fases             | ✅ TERMINADA |
| 3     | Control de Avance Físico (core)        | ✅ TERMINADA |
| 3.1   | Alertas y Dashboard                    | ✅ TERMINADA |
| 3.3   | Semáforos + Drilldowns + Normalización | ✅ TERMINADA |

### 🚧 RELEASE V1.1 — Control Operativo

| Etapa | Nombre                                 | Estado       |
| ----- | -------------------------------------- | ------------ |
| 4.1   | Gastos Adicionales (indirectos)        | ✅ TERMINADA |
| 4.2   | Evidencias (preparado para Flutter)    | ✅ TERMINADA |
| 4.3   | Presupuestos Múltiples + Consolidación | ✅ TERMINADA |
| 4.4   | Facturas → Obras, Analíticas, CFDI XML | ✅ TERMINADA |
| 4.6   | Identificador Obra Pública             | ✅ TERMINADA |
| 4.7   | Reporte Paramétrico                    | ✅ TERMINADA |

### 🚀 RELEASE V1.2 — IA y Flujos Operativos

| Etapa | Nombre                         | Estado       |
| ----- | ------------------------------ | ------------ |
| 5.1   | Chat IA Conversacional + fixes | ✅ TERMINADA |
| 4.5   | Jornales                       | ⏳ Pendiente |
| 5.2   | Flujo aprobación de gastos     | ⏳ Pendiente |
| 5.3   | Fechas y alertas por etapa     | ⏳ Pendiente |
| 5.4   | Resumen granular por fase      | ⏳ Pendiente |
| 5.5   | Perfiles y permisos            | ⏳ Pendiente |

### 🔮 RELEASE V2 — Contabilidad (track separado)

| Etapa | Nombre                                          |
| ----- | ----------------------------------------------- |
| V2.C0 | Bootstrap contable (account + l10n_mx + config) |
| V2.C1 | Integración OCA                                 |
| V2.C2 | UI/folios estilo CONTPAQi                       |
| V2.C3 | Reportería contable                             |
| V2.C4 | Integración Obra ↔ Contabilidad                 |
| V2.C5 | Cierres y auditoría                             |

---

## 9. Detalle de Etapas Futuras

### Etapa 4.2 — Evidencias (para Flutter)

- Modelo: `building.work.evidence`
- Campos: work_id, stage_id, budget_line_id, cost_id, evidence_type, attachment_ids
- Futuro: gps_lat, gps_lng, device_id, captured_at, captured_by
- Smart buttons en Obra/Etapa/Costo para ver evidencias

### Etapa 4.3 — N Presupuestos + Consolidación

- `building.work.budget` (versionado) + `building.work.budget.line`
- Wizard de consolidación: selecciona N presupuestos → snapshot consolidado

### Etapa 4.4 — Factura Proveedor 1→N Obras + 1 CxP

- Cargar factura (PDF/XML) y distribuir a varias obras por % o monto
- Una sola cuenta por pagar
- Alimenta los Gastos Reales (building.real.line) con número de factura
- Llena el KPI "Presupuestado" en Ejecutado Operativo

### Etapa 4.5 — Jornales

- Modelo: `building.work.jornal`
- Campos: work_id, stage_id, worker, date, days, rate, amount, notes

### Etapa 4.6 — Contrato Obra Pública

- Campos adicionales en `building.work`: contract_number, tender, dependencia, fuente financiamiento

---

## 10. Problemas Históricos (EVITAR REPETIR)

1. **Menús rotos**: prompts que crearon menús duplicados o eliminaron existentes
2. **Dashboard no refrescaba**: tras cerrar wizard de avance hasta dar F5
3. **Progressbars desincronizadas**: porcentajes no reflejados en etapas/partidas
4. **Borrado indebido**: en ciertos estados no debe permitir borrados
5. **read_group deprecado**: Odoo 19 usa `_read_group` — ya migrado en financial_engine.py
6. **expand en search**: Odoo 19 no acepta `<group expand="1">` en vistas search

---

## 11. Rol del Agente

Al recibir un prompt para este proyecto, compórtate como:

1. **ANALISTA DE REQUERIMIENTOS SENIOR** — Valida que cada campo, constraint y flujo tenga sentido funcional para un residente de obra que captura datos en campo.

2. **PROGRAMADOR SENIOR ESPECIALIZADO EN ODOO 19 CE** — Conoce la API de Odoo 19 al detalle. Genera códig
