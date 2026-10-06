from app.core.module import BackendModule
from app.modules.painel.router import router

module = BackendModule(name="painel", prefix="/painel", tags=["Visão geral"], router=router,
                       user_stories=['US19', 'US27'])
