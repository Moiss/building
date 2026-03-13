# ORCHESTRATOR.md — OdooBuilding (building_dashboard)
> Ubicación: `/building_dashboard/ORCHESTRATOR.md` (raíz del repo, junto a AGENT.md y CLAUDE.md)
> Uso: Claude Code CLI lee este archivo para dividir una etapa en sub-agentes paralelos

---

## CÓMO ACTIVAR EL ORQUESTADOR

Cuando quieras implementar una etapa completa con sub-agentes paralelos, lanza Claude Code CLI con este comando desde la raíz del repo:

```bash
claude "Lee ORCHESTRATOR.md y el SDD en docs/etapa-X.X.md, luego ejecuta el flujo multi-agente completo"
```

Claude Code leerá este archivo, dividirá el SDD en 4 contratos y lanzará los agentes en paralelo usando Git Worktrees.

---

## ROL DEL ORQUESTADOR

El orquestador **NUNCA escribe código directamente**. Su único trabajo es:
1. Leer el SDD de la etapa (`docs/etapa-X.X.md`)
2. Extraer los contratos de cada agente
3. Crear las ramas Git con Worktrees
4. Lanzar los 4 sub-agentes en paralelo
5. Esperar sus outputs
6. Reportar al humano para aprobación

---

## SETUP DE GIT WORKTREES

El orquestador ejecuta esto antes de lanzar los agentes:

```bash
# Asegurarse de estar en main actualizado
git checkout main && git pull origin main

# Crear 3 worktrees independientes (uno por agente que escribe código)
git worktree add ../building-models etapa-X.X-models
git worktree add ../building-views  etapa-X.X-views
git worktree add ../building-tests  etapa-X.X-tests
# El agente de seguridad NO necesita worktree — solo audita, no escribe código

# Verificar worktrees activos
git worktree list
```

---

## LOS 4 SUB-AGENTES

### AGENTE A — Modelos Python
**Rama:** `etapa-X.X-models`
**Carpeta de trabajo:** `../building-models/models/`
**Archivos que puede tocar:** SOLO `models/*.py` y `models/__init__.py`

**Contrato de entrada (lo que recibe del SDD):**
```
- Nombre del modelo (_name: building.work.xxx)
- Campos con tipo, string, help
- Relaciones con modelos existentes
- Lógica del motor (si afecta financial_engine.py o progress_engine.py)
- Reglas de negocio (@api.constrains, @api.depends)
```

**Contrato de salida (lo que entrega):**
```
- Archivo models/nombre_modelo.py completo
- Docstrings en español en cada clase y método
- _name, _description, _order en cada modelo nuevo
- index=True en campos de búsqueda frecuente
- tracking=True en campos de auditoría
- Si afecta el motor: actualizar financial_engine.py o progress_engine.py
- Validado con: python3 -m py_compile models/nombre_modelo.py
```

**Restricciones absolutas para Odoo 19 CE:**
- NUNCA modificar modelos nativos Odoo — siempre _inherit
- NUNCA usar read_group() — usar _read_group() (Odoo 19)
- NUNCA mezclar Gastos Reales (building.real.line) con Gastos Adicionales (building.work.cost)
- NUNCA usar _sql_constraints — usar models.Constraint()
- NO poner percent_weight en building.work.stage (no existe)
- NO usar state='planned' — usar state='planning'
- building.budget.line NO tiene unit_id, quantity, unit_price

---

### AGENTE B — Vistas XML
**Rama:** `etapa-X.X-views`
**Carpeta de trabajo:** `../building-views/views/`
**Archivos que puede tocar:** SOLO `views/*.xml` y `views/menus.xml`

**Contrato de entrada (lo que recibe del Agente A):**
```
- Lista exacta de campos del modelo (nombre, tipo, string)
- Nombre del modelo (_name)
- Grupos de seguridad (building_user / building_manager / etc.)
- Tipo de vista requerida (list, form, kanban, search)
- Smart buttons requeridos en building_work_views.xml (si aplica)
```

**Contrato de salida (lo que entrega):**
```
- Archivo views/building_nombre_views.xml con list + form + search
- XML IDs únicos (verificado con grep -rn "record id=" views/)
- UI profesional: badges coloreados, íconos circulares, Bootstrap 5
- Smart button actualizado en building_work_views.xml (si aplica)
- Menú agregado en menus.xml SOLO si el SDD lo indica explícitamente
```

**Restricciones absolutas para Odoo 19 CE:**
- SIEMPRE <list> — NUNCA <tree>
- SIEMPRE invisible="condicion" — NUNCA attrs="{...}"
- NO <group expand="1"> en vistas search
- NO duplicar XML IDs — verificar con grep primero
- NO tocar menus.xml sin instrucción explícita (problema histórico)
- NO crear vistas para modelos que ya tienen vista

---

### AGENTE C — Tests Unitarios
**Rama:** `etapa-X.X-tests`
**Carpeta de trabajo:** `../building-tests/tests/`
**Archivos que puede tocar:** SOLO `tests/test_*.py` y `tests/__init__.py`

**Contrato de entrada (lo que recibe del Agente A):**
```
- Modelo a testear (_name)
- Campos críticos y sus validaciones
- Acceptance Criteria del SDD (AC-01, AC-02...)
- Grupos de seguridad existentes
```

**Tests mínimos obligatorios por tipo de modelo:**

Para modelos de **obra/presupuesto** (`building.work`, `building.budget.*`):
```python
# - test_create_work: creación exitosa con campos requeridos
# - test_budget_totals: totales calculados correctamente por el motor
# - test_stage_states: transiciones de estado válidas
# - test_access_user: usuario normal puede crear/leer
# - test_access_manager: manager puede hacer todo
```

Para modelos de **gastos** (`building.work.cost`, `building.real.line`):
```python
# - test_create_cost: gasto adicional con cost_type forzado a 'additional'
# - test_no_physical_progress: gasto NO afecta avance físico
# - test_engine_totals: motor financiero suma correctamente
# - test_smart_button_count: contador en obra correcto
```

Para modelos de **motor** (`financial_engine`, `progress_engine`):
```python
# - test_read_group_aggregation: _read_group retorna datos correctos
# - test_performance_bulk: motor con 100+ registros en < 2s
# - test_traffic_light: semáforos correcto en cada escenario
```

**Contrato de salida:**
```
- Archivo tests/test_nombre_modelo.py
- @tagged('post_install', '-at_install', 'building_dashboard')
- TransactionCase con setUpClass y datos reutilizables
- Mínimo 5 tests por archivo
- Comando de ejecución documentado
```

**Comando de ejecución:**
```bash
python odoo-bin \
  -c /Users/macbookpro/odoo/odoo19ce/proyectos/building_dashboard/odoo.conf \
  -d building_dashboard \
  --test-enable --test-tags /building_dashboard \
  --stop-after-init
```

---

### AGENTE D — Auditoría de Seguridad
**Rama:** ninguna — solo audita, NO escribe código
**Trabaja sobre:** los outputs de A, B y C en modo lectura

**Contrato de salida (reporte estructurado):**
```markdown
## Reporte de Seguridad — Etapa X.X
Fecha: YYYY-MM-DD

### 🔴 CRÍTICO (bloquea el PR)
- [ ] Item: descripción + archivo + línea + fix sugerido

### 🟡 ADVERTENCIA (revisar antes de producción)
- [ ] Item: descripción + archivo + recomendación

### 🟢 VERIFICADO OK
- Gastos Reales ≠ Gastos Adicionales: ✅ no mezclados
- company_id en modelos operativos: ✅
- Sin secrets/API keys hardcodeadas: ✅
- ACL en ir.model.access.csv para modelos nuevos: ✅
- Record Rules en ir_rule.xml: ✅
- _read_group usado (no read_group): ✅
- Sin <tree> en vistas: ✅
- Sin attrs= deprecated: ✅
- API keys IA cifradas (encryption_service.py): ✅
```

**Qué revisa específicamente en Building:**
- API keys de Claude/Gemini/OpenAI sin cifrar (deben usar `encryption_service.py`)
- Métodos del asistente IA que expongan keys en logs
- Campos `_create_work_from_json()` con campos no permitidos (ver CLAUDE.md sección 7)
- Modelos sin ACL en `ir.model.access.csv`
- Motores que usan `read_group` en vez de `_read_group`
- Vistas con `expand="1"` (rompe en Odoo 19)
- Mezcla accidental de flujos: `building.real.line` y `building.work.cost`
- SQL injection en queries dinámicas
- Datos de obra expuestos a usuarios de otras empresas (Record Rules)

---

## FLUJO COMPLETO PASO A PASO

```
1. Tú (Claude Web) generas docs/etapa-X.X.md (el SDD)
   ↓
2. Claude Code CLI lee ORCHESTRATOR.md + el SDD
   ↓
3. Orquestador crea 3 worktrees y lanza A, B, C en paralelo
   (D espera a que A y B terminen para auditar)
   ↓
4. A: escribe models/ | B: escribe views/ | C: escribe tests/
   (simultáneamente, sin colisiones)
   ↓
5. D audita los 3 outputs y genera reporte
   ↓
6. Orquestador presenta reporte completo al humano (tú)
   ↓
7. Tú revisas — apruebas o pides correcciones por agente
   ↓
8. Upgrade local para verificar:
   python odoo-bin -c odoo.conf -d building_dashboard -u building_dashboard
   ↓
9. Se abren 3 PRs → GitHub Actions valida (lint + tests + security)
   ↓
10. Tú haces merge a main
    ↓
11. Limpiar worktrees:
    git worktree remove ../building-models
    git worktree remove ../building-views
    git worktree remove ../building-tests
```

---

## CONTRATOS DE RESULTADO — FORMATO JSON

```json
{
  "agente": "A_modelos",
  "etapa": "X.X",
  "estado": "completado",
  "archivos_creados": ["models/building_work_nuevo.py"],
  "archivos_modificados": ["models/__init__.py", "models/financial_engine.py"],
  "validacion": "python3 -m py_compile OK",
  "campos_exportados": [
    {"nombre": "work_id", "tipo": "Many2one", "modelo": "building.work", "required": true},
    {"nombre": "amount_total", "tipo": "Float", "compute": true, "store": true}
  ],
  "motor_afectado": "financial_engine.py",
  "notas": "Agrega get_nuevo_total() al motor. 2 constrains. tracking=True en campos clave."
}
```

---

## CUÁNDO NO USAR EL ORQUESTADOR

| Tarea | Usar orquestador | Usar directamente |
|---|---|---|
| Nueva etapa con modelo + vista + tests | ✅ | |
| Refactor del motor financiero | ✅ | |
| Fix de un bug puntual | | ✅ Antigravity |
| Cambio de label o color en vista | | ✅ Antigravity |
| Pregunta sobre el código | | ✅ Claude Web |
| Generar SDD de la etapa | | ✅ Claude Web |
| Fix del asistente IA (building_ai_chat.py) | | ✅ Antigravity (es delicado) |

---

*Actualizar este archivo si cambia la estructura del repo, los grupos de seguridad o el motor de cálculo.*
*Última revisión: 2026-03-13*
