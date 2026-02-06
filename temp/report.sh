
cat > /Users/macbookpro/odoo/odoo19ce/proyectos/generate_reports.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/macbookpro/odoo/odoo19ce/proyectos"
OUT="$ROOT/reports"
mkdir -p "$OUT"

cd "$ROOT"

echo "[1/3] assign/wizard..."
rg -n "building\\.budget\\.line|class .*BudgetLine|action_.*assign|assign|cargar|capit|chapter|stage_id|create\\(|write\\(" -S . \
  | tee "$OUT/01_assign_wizard.txt" >/dev/null

echo "[2/3] engine/compute..."
rg -n "_compute_|semafor|traffic|consum|desviaci|distribu|difference|distributed|rollup" -S . \
  | tee "$OUT/02_engine_compute.txt" >/dev/null

echo "[3/3] constraints..."
rg -n "sql_constraints|_sql_constraints|unique" -S . \
  | tee "$OUT/03_constraints.txt" >/dev/null

echo "Done. Reports saved in: $OUT"
ls -lh "$OUT"
EOF
