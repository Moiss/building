# QA Checklist - HARDENING Stage 0 -> 3.3.2

## Objetivo

Verificar el endurecimiento del flujo Presupuesto -> Etapas, la eliminación de duplicados y el versionado.

## 1. Pruebas de Configuración y Normalización

- [ ] **Crear Partida (Manual)**
  - [ ] Ir a Presupuesto -> Capítulos -> Agregar Partida.
  - [ ] Ingresar código en minúsculas (ej: `muro-01`). Al guardar, debe cambiar a `MURO-01`.
  - [ ] Ingresar nombre con espacios raros (ej: `muro   de   contencion`). Al guardar, debe cambiar a `Muro De Contencion`.
- [ ] **Restricción de Duplicados (SQL)**
  - [ ] Intentar asignar manualmente (por código/interfaz) una partida a una etapa donde YA existe esa partida (misma `base_budget_line_id`).
  - [ ] Debe saltar error de integridad/Odoo "Validation Error".

## 2. Wizard "Cargar Capítulo" (Refactorizado)

- [ ] **Carga Inicial**
  - [ ] Presupuesto Validado.
  - [ ] Etapa -> Acción "Cargar desde Capítulo".
  - [ ] Seleccionar capítulos. Modo: "Omitir" o "Sync".
  - [ ] **Resultado**: Se crean las partidas en la etapa.
- [ ] **Idempotencia (Carga Repetida)**
  - [ ] Ejecutar el wizard DE NUEVO con los mismos capítulos.
  - [ ] **Resultado**: NO se deben duplicar las líneas. Debe decir "Omitidas: X" o "Actualizadas: X".
- [ ] **Asignación con Presupuesto Validado**
  - [ ] Confirmar que el wizard funcionó aunque el presupuesto esté en estado `validated`.

## 3. Versionado de Presupuesto

- [ ] **Validación V1**
  - [ ] Crear Presupuesto nuevo. Estado Borrador.
  - [ ] Validar. Cambia a `validated`.
  - [ ] Chatter muestra: "Presupuesto cerrado: V1 ...".
- [ ] **Re-cierre V2**
  - [ ] Reabrir presupuesto (Botón "Reabrir" - requiere permisos Director).
  - [ ] Modificar algo (opcional).
  - [ ] Validar de nuevo.
  - [ ] Chatter muestra: "Presupuesto cerrado: V2 ...".

## 4. Drill-down UX

- [ ] **Desde Etapa**
  - [ ] Botón Inteligente/Acción "Partidas de la Etapa". Debe abrir lista filtrada solo por esa etapa.
  - [ ] Botón "Movimientos Reales". Debe abrir lista filtrada.

## 5. Limpieza (Si aplica)

- [ ] Ejecutar script de limpieza `cleanup_duplicates.py` en base de datos con duplicados previos.
- [ ] Verificar que quedan solo los "Winners" (con avance).
