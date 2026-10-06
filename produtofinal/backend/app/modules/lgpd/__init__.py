from app.core.module import BackendModule
from app.modules.lgpd.router import router

module = BackendModule(name="lgpd", prefix="/lgpd", tags=["Eixo 2 · Dados pessoais (LGPD)"],
                       router=router, user_stories=["US11", "US12", "US13", "US26", "US27"])
