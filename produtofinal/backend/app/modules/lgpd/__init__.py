from app.core.config import get_settings
from app.core.module import BackendModule, JobSpec
from app.modules.lgpd.router import router
from app.modules.lgpd.service import job_varredura_incremental

module = BackendModule(
    name="lgpd", prefix="/lgpd", tags=["Eixo 2 · Dados pessoais (LGPD)"], router=router,
    jobs=[JobSpec(id="varredura_incremental", func=job_varredura_incremental,
                  cron=get_settings().lgpd_varredura_cron)],
    user_stories=["US11", "US12", "US13", "US26", "US27"],
)
