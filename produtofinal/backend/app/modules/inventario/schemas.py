from datetime import datetime

from pydantic import BaseModel


class ColetaOut(BaseModel):
    id: int
    iniciada_em: datetime
    finalizada_em: datetime | None
    status: str
    origem: str
    solicitada_por: str | None
    total_organizacoes: int
    total_datasets: int
    total_recursos: int
    erro: str | None

    model_config = {"from_attributes": True}
