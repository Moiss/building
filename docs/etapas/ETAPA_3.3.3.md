# Etapa 3.3.3

Fecha: 2026-02-06
Rama: etapa-3.3.3
Scope: Fix refresh (sin F5) tras registrar avance físico

## Objetivo

Lograr que el Dashboard de Obra (y la vista subyacente) se refresque automáticamente después de registrar un avance físico, eliminando la necesidad de refrescar manualmente la página (F5).

## Checklist de Entregables

- [x] Análisis de arquitectura (OWL vs Estándar) completado
- [x] Solución Capa 1 (Reload Action) implementada
- [x] Solución Capa 2 (Bus/JS) implementada (N/A)
- [x] QA-1: Registro simple actualiza UI
- [x] QA-2: Registros secuenciales funcionan
- [x] QA-3: Dashboard actualizado al cerrar modal
- [x] QA-4: Cross-tab update (N/A)

## Cambios Clave

- **Modelos**: `wizards/building_budget_progress_wizard.py` retorna `tag: reload`.
- **Frontend**: N/A (Vista estándar).

## Notas de QA

- **Realizadas**: Verificación estática. La acción `reload` fuerza el refresco de la vista cliente estándar al cerrar el wizard.
- **Pendientes**: N/A

## Rollback

```bash
git checkout main
git branch -D etapa-3.3.3
```
