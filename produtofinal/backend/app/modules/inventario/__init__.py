from app.core.config import get_settings
from app.core.module import BackendModule, JobSpec
from app.modules.inventario.router import router
from app.modules.inventario.service import job_coleta_diaria

module = BackendModule(
    name="inventario", prefix="/inventario", tags=["Inventário CKAN"], router=router,
    jobs=[JobSpec(id="coleta_diaria", func=job_coleta_diaria, cron=get_settings().coleta_cron)],
    user_stories=["US5", "US23"],
)
