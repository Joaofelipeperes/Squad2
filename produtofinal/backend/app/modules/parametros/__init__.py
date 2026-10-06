from app.core.module import BackendModule
from app.modules.parametros.router import router

module = BackendModule(name="parametros", prefix="/parametros",
                       tags=["Administração · Parâmetros"], router=router,
                       user_stories=["US8", "US11", "US16", "US17"])
