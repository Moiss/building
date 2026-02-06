Eres Antigravity. Estás en Odoo 19 CE.

REGLAS ODOO 19 (OBLIGATORIAS)

- Vistas de lista: usar <list>. Prohibido <tree>.
- Antes de heredar vistas: localizar IDs reales (ir.ui.view) y NO inventar inherit_id/xpath.
- Assets: declarar en **manifest**.py (assets) y respetar reglas de replace/remove: el asset debe existir previamente.
- UI moderna: usar OWL cuando aplique, cargado por assets bundle.

OBJETIVO
[Describe el cambio: p.ej. “Refactor de avances con motor global”, “Dashboard OWL”, etc.]

ALCANCE

1. Backend (Python):
   - Implementar/ajustar modelos/métodos/constraints.
2. UI (XML):
   - Actualizar vistas form/list/kanban/search según aplique.
   - Listas siempre con <list>.
3. Seguridad:
   - ACL + record rules mínimos necesarios.
4. Pruebas:
   - SavepointCase para lógica
   - (Opcional) Tour si se requiere validar el flujo UI.

CALIDAD / NO BASURA

- Eliminar duplicidades.
- No dejar código comentado.
- Si un campo ya existe en BD, deprecar en vez de borrar (readonly + fuera de vistas), salvo que haya migración.
- Dejar nota TECH_NOTES.md con “Removed/Deprecated/Replaced by”.
