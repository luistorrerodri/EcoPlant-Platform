import uuid

from pydantic import BaseModel


class PlantTypeOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    default_humedad_min: int
    default_hora_inicio: int
    default_hora_fin: int
    default_duracion_riego_ms: int

    model_config = {"from_attributes": True}
