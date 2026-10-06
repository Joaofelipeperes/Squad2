from app.core.module import BackendModule
from app.modules.envio.router import router

module = BackendModule(name="envio", prefix="/envio", tags=["Órgão publicador · envio de dados"],
                       router=router, user_stories=[])
