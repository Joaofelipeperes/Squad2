from app.core.module import BackendModule
from app.modules.atualizacoes.router import router

module = BackendModule(name="atualizacoes", prefix="/atualizacoes", tags=["Eixo 1 · Atualizações"], router=router,
                       user_stories=['US9', 'US10'])
