from app.core.module import BackendModule
from app.modules.metadados.router import router

module = BackendModule(name="metadados", prefix="/metadados", tags=["Eixo 2 · Metadados e formatos"], router=router,
                       user_stories=['US16', 'US17'])
