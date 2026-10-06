from app.core.module import BackendModule
from app.modules.rastreabilidade.router import router

module = BackendModule(name="rastreabilidade", prefix="/rastreabilidade", tags=["Eixo 1 · Rastreabilidade"], router=router,
                       user_stories=['US14', 'US29'])
