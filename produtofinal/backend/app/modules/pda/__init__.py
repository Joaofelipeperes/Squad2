from app.core.module import BackendModule
from app.modules.pda.router import router

module = BackendModule(name="pda", prefix="/pda", tags=["Eixo 1 · Monitoramento do PDA"], router=router,
                       user_stories=['US6', 'US7', 'US8'])
