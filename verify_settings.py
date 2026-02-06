
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def run(env):
    """
    Script de Verificación: Acceso a Res Config Settings
    """
    print("[VERIFICACIÓN] Intentando acceder a res.config.settings...")
    
    try:
        Settings = env['res.config.settings']
        # Simular default_get que hace la vista
        fields = ['building_encryption_key', 'budget_real_threshold_warning', 'building_default_real_source']
        defaults = Settings.default_get(fields)
        print(f"[OK] default_get exitoso. Defaults: {defaults}")
        
        # Simular onchange (si existiera lógica) o create
        settings = Settings.create(defaults)
        print(f"[OK] create exitoso. ID: {settings.id}")
        
        print(f"[CHECK] building_default_real_source: {settings.building_default_real_source}")
        
    except Exception as e:
        print(f"[ERROR] Falló el acceso a settings: {e}")
        import traceback
        traceback.print_exc()

    env.cr.rollback()
    print("[CLEANUP] Rollback realizado.")

if __name__ == '__main__':
    run(env)
