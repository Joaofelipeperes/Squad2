from app.core.module import BackendModule
from app.modules.acesso.router import router

module = BackendModule(name="acesso", prefix="/acesso", tags=["Acesso · usuários e papéis"],
                       router=router, user_stories=["US24"])
