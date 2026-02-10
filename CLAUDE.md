# CLAUDE.md — Proyecto OdooBuilding (módulo: building_dashboard)

> **Fuente única de verdad** para que Claude Code entienda el proyecto,
> lo ya implementado, la arquitectura y lo que sigue.

---

## 1. ¿Qué es OdooBuilding?

Vertical de **Odoo 19 Community Edition** para **control de obras de construcción**.
El módulo principal se llama `building_dashboard`.

El core actual cubre:

- Alta de Obras
- Presupuestos y Partidas
- Planeación por Etapas/Fases
- Control de Avance Físico con semáforos, dashboard, alertas y drilldowns

---

## 2. Stack Técnico y Reglas del Proyecto

- **Odoo 19 Community Edition** (NO Enterprise)
- **Python 3** (modelos, lógica, wizards)
- **XML** (vistas, menús, acciones, seguridad)
- **PostgreSQL** (base de datos Odoo)
- En Odoo 19 las vistas de lista usan `<list>` (NO `<tree>`)
- El desarrollador es principiante en Odoo/Python:
  - **Siempre incluir comentarios explicativos en el código**
  - **Explicar qué hace cada función/método**
  - **Comentar las relaciones entre modelos**

### Política de entregables por etapa

Cada etapa debe incluir:

1. **Walkthrough** (paso a paso de uso)
2. **Implementation plan** (plan de implementación)
3. **Tasks** (checklist de tareas)
4. **QA** (pruebas obligatorias)

Todo en **ESPAÑOL**.

### Palabra clave para prompts avanzados

`MODO FACTURAR`

---

## 3. Arquitectura: Motor de Cálculo (Engine)

### Principio clave

Existe un **motor/engine** que centraliza los cálculos de rollups para dashboards:

- Totales y porcentajes agregados
- Drilldowns
- Semáforos

### Reglas del motor

1. Los **"show fields"** (campos visibles en Obra/Etapa) → `compute` + `store=True` para performance
2. La **lógica de rollup se centraliza en el motor**, NO se duplica en múltiples modelos
3. Los modelos transaccionales solo calculan lo básico del registro individual
4. El motor usa **`read_group`** para performance en agregados
5. **CRÍTICO**: Motor de costos ≠ Motor de avance (3.x) → son módulos lógicos **SEPARADOS**

### Ejemplo aplicado (Etapa 4.1 — Costos)

- `building.work.cost` calcula `amount = qty * unit_cost` (nivel registro)
- El **motor** calcula `executed_*` por obra usando `read_group` (nivel agregado)

---

## 4. Reglas Funcionales (NO olvidar)

1. **Avance físico ≠ Costos**
   - Avance físico (Etapa 3.x): porcentajes y semáforos de progreso
   - Costos (Etapa 4.1): ejecutado presupuestado/adicional, desviación
2. Los **"adicionales"** (clavos, resistol, silicón) pueden ocurrir en cualquier etapa pero **NO incrementan avance físico**
3. La UI debe ser **rápida**: agregados por motor con `read_group` + campos `store`
4. **QA siempre obligatorio** por etapa
5. Evitar que cambios **rompan menús** o **dupliquen vistas** (problema histórico del proyecto)

---

## 5. Modelos Core (lo que ya existe)

> Los nombres exactos pueden variar. Revisar archivos reales en `models/`.

### `building.work` (Obra)

- Nombre/identificación de la obra
- Estado de obra
- Relaciones a etapas
- Dashboard / métricas (avance, semáforos, etc.)

### `building.work.stage` (Etapa/Fase de la obra)

- Obra (relación)
- Fechas planeadas
- Avance físico (campos usados por engine)
- Estado

### `building.budget.line` (Partida de presupuesto)

- Obra
- Etapa (a veces)
- `amount` (presupuestado)
- `executed_amount` (ejecutado)
- `physical_progress` (si existe en ese nivel)
- Relaciones para drilldown

### Wizards de captura de avance (Etapa 3.x)

- Registrar avance por etapa / global
- Recalcular dashboard

---

## 6. Roadmap Completo

### ✅ RELEASE V1 — Operación de Obra (sin contabilidad)

| Etapa | Nombre                                 | Estado                   |
| ----- | -------------------------------------- | ------------------------ |
| 0     | Bootstrap / Base                       | ✅ TERMINADA             |
| 1     | Presupuesto estructurado               | ✅ TERMINADA             |
| 2     | Planeación de Etapas/Fases             | ✅ TERMINADA             |
| 3     | Control de Avance Físico (core)        | ✅ TERMINADA hasta 3.3.x |
| 3.1   | Alertas y Dashboard                    | ✅                       |
| 3.3   | Semáforos + Drilldowns + Normalización | ✅ (detalles menores)    |

### 🚧 RELEASE V1.1 — Control Operativo

| Etapa | Nombre                                         | Estado       | Prioridad |
| ----- | ---------------------------------------------- | ------------ | --------- |
| 4.1   | Costos operativos (adicionales/presupuestados) | 🆕 SIGUIENTE | 1         |
| 4.2   | Evidencias (preparado para Flutter)            | Pendiente    | 2         |
| 4.6   | Identificador obra pública (contrato)          | Pendiente    | 3         |
| 4.5   | Jornales (días de trabajo)                     | Pendiente    | 4         |
| 4.3   | N Presupuestos + Consolidación                 | Pendiente    | 5         |
| 4.4   | Factura proveedor 1→N obras + 1 CxP            | Pendiente    | 6         |

### 🔮 RELEASE V2 — Contabilidad (track separado)

| Etapa | Nombre                                                 |
| ----- | ------------------------------------------------------ |
| V2.C0 | Bootstrap contable (account + l10n_mx + config)        |
| V2.C1 | Integración OCA (repos/módulos clave)                  |
| V2.C2 | UI/folios estilo CONTPAQi                              |
| V2.C3 | Reportería contable (balanza, mayor, auxiliares, EEFF) |
| V2.C4 | Integración Obra ↔ Contabilidad                        |
| V2.C5 | Cierres y auditoría                                    |

---

## 7. Detalle Etapa 4.1 — Costos Operativos (SIGUIENTE A IMPLEMENTAR)

### Objetivo

Registrar consumos y gastos operativos, incluyendo "adicionales" que pueden ocurrir
en cualquier fase, pero **NO afectan avance físico**.

### Modelo: `building.work.cost`

```python
# Campos principales:
# - work_id          → Many2one a building.work (requerido)
# - stage_id         → Many2one a building.work.stage (opcional)
# - cost_type        → Selection: 'budgeted' / 'additional'
# - budget_line_id   → Many2one a building.budget.line
#                      (obligatorio si budgeted, prohibido si additional)
# - product_id       → Many2one a product.product (opcional)
# - description      → Char
# - qty              → Float
# - unit_cost        → Float
# - amount           → Float, compute, store (qty * unit_cost)
```

### Campos agregados en `building.work`

```python
# Calculados por el MOTOR (engine), NO por el modelo directamente:
# - executed_budgeted_amount   → Float, compute, store
# - executed_additional_amount → Float, compute, store
# - executed_total_amount      → Float, compute, store
# - cost_count                 → Integer, compute, store
```

### Motor de costos

```python
# engine.get_cost_totals(work_ids)
# Usa read_group agrupando por work_id + cost_type
# Suma amount y cuenta registros
```

### UI

- Menú: Obras → Operación → Costos de Obra
- Vistas: `<list>`, `<form>`, `<search>` (Odoo 19: NO usar `<tree>`)
- Smart button "Costos" en la vista form de Obra (con contador + totales)

### Seguridad

- Grupos: `cost_user` / `cost_manager`
- ACL + record rules multi-company

### QA crítico

- [ ] Crear costo adicional y presupuestado → confirmar que avance físico NO cambia
- [ ] Totales correctos en obra
- [ ] Performance con miles de costos
- [ ] Smart button funcional con conteo correcto
- [ ] Filtros y agrupaciones en vista search

---

## 8. Detalle Etapa 4.2 — Evidencias (para Flutter)

### Modelo: `building.work.evidence`

- `work_id` (required)
- `stage_id` (opcional)
- `budget_line_id` (opcional)
- `cost_id` (opcional)
- `evidence_type` (selection)
- `attachment_ids` (Many2many a `ir.attachment`)
- `captured_at`, `captured_by`
- Futuro: `gps_lat`, `gps_lng`, `device_id`

### UI

- Smart buttons en Obra/Etapa/Costo para ver evidencias
- Vistas filtradas por obra/etapa/tipo

---

## 9. Detalle Etapa 4.3 — N Presupuestos + Consolidación

- `building.work.budget` (versionado) + `building.work.budget.line`
- Wizard de consolidación: selecciona N presupuestos validados → genera snapshot consolidado
- Trazabilidad de origen

---

## 10. Detalle Etapa 4.4 — Factura Proveedor 1→N Obras + 1 CxP

- Cargar factura (PDF/XML) y distribuir a varias obras por % o monto
- Una sola cuenta por pagar
- Opción A: reusar analítica Odoo (mínimo contable)
- Opción B: modelo propio `vendor.bill` + `allocation_lines` + payable única

---

## 11. Detalle Etapa 4.5 — Jornales

- Modelo: `building.work.jornal`
  - `work_id`, `stage_id`, `employee/worker`, `date`, `days`, `rate`, `amount`, `notes`
- Opción: custom o reusar timesheets

---

## 12. Detalle Etapa 4.6 — Contrato Obra Pública

Campos en `building.work`:

- `contract_number`
- `tender` / expediente (opcional)
- Dependencia / ente contratante
- Fuente de financiamiento
- Fechas y monto autorizado (opcionales)

---

## 13. Problemas Históricos (evitar repetir)

1. **Menús rotos**: prompts que "desmadraron" menús/acciones en base nueva
2. **Dashboard no refrescaba**: al cerrar wizard de avance hasta dar F5
3. **Progressbars desincronizadas**: porcentajes no se reflejaban en ciertas etapas/partidas
4. **Borrado indebido**: en ciertos estados no debe permitir borrados (ocultar botón eliminar según estado)
5. **Vistas duplicadas**: al regenerar XML sin verificar IDs existentes

---

## 14. Dev Workflow

- Se trabaja por **etapas y sub-etapas**
- Cada etapa se implementa con un **prompt** que incluye: walkthrough + plan + tasks + QA
- **Recomendación**: branches por etapa (`etapa-4.1`, `etapa-4.2`, etc.) para rollback fácil
- Evitar que prompts rompan menús o dupliquen vistas
- El código generado por IA debe ser **revisado y probado** antes de merge

---

## 15. Convenciones de Código

```python
# ═══════════════════════════════════════════════════════════════
# SIEMPRE:
# - Comentar cada clase explicando su propósito
# - Comentar cada método explicando qué hace
# - Comentar campos no obvios
# - Usar docstrings en español
# - Seguir naming conventions de Odoo (building.work.xxx)
# - Usar _name, _description, _order en cada modelo
# ═══════════════════════════════════════════════════════════════

# Ejemplo de estilo esperado:
class BuildingWorkCost(models.Model):
    """
    Modelo para registrar costos operativos de obra.
    Incluye costos presupuestados y adicionales.
    NO afecta el avance físico de la obra.
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

## 16. Estructura esperada del módulo

```
building_dashboard/
├── __init__.py
├── __manifest__.py
├── CLAUDE.md                       ← ESTE ARCHIVO
├── models/
│   ├── __init__.py
│   ├── building_work.py            # Modelo principal de Obra
│   ├── building_work_stage.py      # Etapas/Fases
│   ├── building_budget_line.py     # Partidas de presupuesto
│   ├── building_work_cost.py       # 🆕 4.1 Costos operativos
│   ├── building_work_evidence.py   # 🆕 4.2 Evidencias
│   ├── building_work_jornal.py     # 🆕 4.5 Jornales
│   └── engine/                     # Motor de cálculo
│       ├── __init__.py
│       ├── progress_engine.py      # Motor de avance físico (3.x)
│       └── cost_engine.py          # 🆕 Motor de costos (4.1)
├── views/
│   ├── building_work_views.xml
│   ├── building_stage_views.xml
│   ├── building_cost_views.xml     # 🆕 4.1
│   ├── building_evidence_views.xml # 🆕 4.2
│   └── menu.xml
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── wizards/                        # Wizards de captura
├── data/                           # Datos iniciales
└── static/                         # Assets
```

---

## 17. Instrucciones para Claude Code

Al iniciar en este proyecto:

1. **Lee este archivo primero** — es tu contexto base
2. **Revisa `models/`** — compara con lo documentado aquí y ajusta tu entendimiento
3. **Revisa `views/`** — identifica menús y vistas existentes para no duplicar
4. **Revisa `security/`** — identifica grupos y ACL existentes
5. **Antes de crear archivos nuevos**, verifica que no existan ya
6. **Antes de modificar menús/vistas**, revisa XML IDs existentes
7. **Todo código nuevo** debe seguir las convenciones de la sección 15
8. **Todo entregable** debe incluir walkthrough + plan + tasks + QA en español
