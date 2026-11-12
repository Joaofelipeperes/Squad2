from app.core.config import get_settings
from app.core.module import BackendModule, JobSpec
from app.modules.backup.service import job_diario, job_limpeza, job_mensal

# Sem router: os backups são internos, ainda sem tela nem rota (ADR-0034).
module = BackendModule(
    name="backup", prefix="/backup", tags=["Administração · Backups"],
    jobs=[JobSpec(id="diario", func=job_diario, cron=get_settings().backup_diario_cron),
          JobSpec(id="mensal", func=job_mensal, cron=get_settings().backup_mensal_cron),
          JobSpec(id="limpeza", func=job_limpeza, cron=get_settings().backup_limpeza_cron)],
    user_stories=[],
)
