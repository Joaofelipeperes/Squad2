from app.core.module import BackendModule
from app.modules.ia.router import router

module = BackendModule(name="ia", prefix="/ia", tags=["Administração · Modelos de IA"],
                       router=router, user_stories=["US11", "US28"])
