from app.core.module import BackendModule
from app.modules.ckan_config.router import router

module = BackendModule(name="ckan_config", prefix="/ckan-config",
                       tags=["Administração · Configurações CKAN"], router=router,
                       user_stories=["ADR-0024"])
