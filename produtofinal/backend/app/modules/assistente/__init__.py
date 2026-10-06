from app.core.module import BackendModule
from app.modules.assistente.router import router

module = BackendModule(name="assistente", prefix="/assistente", tags=["Assistente GEDA"],
                       router=router, user_stories=["US28"])
