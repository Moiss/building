# Etapa 4.1: Gestión de Costos Operativos

**Rama**: `etapa-4.1`

## Scope

Implementación del módulo de gestión de costos operativos, permitiendo el registro y control de gastos directos (presupuestados) e indirectos (adicionales) asociados a la obra.

## Objetivo

Proporcionar una herramienta para registrar los costos reales incurridos en la obra, clasificándolos adecuadamente y actualizando en tiempo real los indicadores financieros del proyecto (Ejecutado vs Presupuestado).

## Checklist de Entregables

- [x] Modelo `building.work.cost` creado con campos necesarios.
- [x] Tipos de costo: `budgeted` (presupuestado) y `additional` (adicional).
- [x] Constraints de validación:
  - [x] `budgeted` requiere `budget_line_id`.
  - [x] `additional` no permite `budget_line_id`.
- [x] Vistas de Costos: Tree y Form.
- [x] Integración con `building.work`:
  - [x] Pestaña "Costos" en la vista de Obra.
  - [x] Campos computados: `executed_budgeted_amount`, `executed_additional_amount`, `executed_total_amount`.
- [x] Script de verificación QA (`verify_stage_4_1.py`) aprobado.

## Cambios Clave

- **Nuevo Modelo**: `models/work_cost.py` (`building.work.cost`).
- **Actualización Modelo**: `models/building_work.py` (cálculo de totales ejecutados).
- **Vistas**: `views/work_cost_views.xml` y actualización de `views/building_work_views.xml`.
- **Seguridad**: Reglas de acceso en `ir.model.access.csv`.

## Notas de QA

- **Pruebas Realizadas**:
  1.  Creación de costos adicionales (Indirectos) -> Actualiza `executed_additional_amount` y `executed_total_amount`.
  2.  Creación de costos presupuestados (Directos) -> Requiere partida, actualiza `executed_budgeted_amount`.
  3.  Validación de Constraints (Bloqueo de registros inválidos).
  4.  Modificación y Eliminación -> Recálculo correcto de totales.
  5.  Independencia del Avance Físico (El registro de costos no altera el % de avance físico).

## Rollback

```bash
git checkout main
git branch -D etapa-4.1
```
