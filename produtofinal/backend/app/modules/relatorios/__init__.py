from app.core.module import BackendModule
from app.modules.relatorios.router import router

module = BackendModule(name="relatorios", prefix="/relatorios", tags=["Relatórios"], router=router,
                       user_stories=['US20'])
