import uuid
from datetime import datetime

from pydantic import BaseModel


class HealthSummaryOut(BaseModel):
    id: uuid.UUID
    device_id: str
    window_days: int
    verdict: str
    message: str
    pct_tiempo_bajo_minimo: float | None
    pct_tiempo_saturado: float | None
    num_riegos: int | None
    tiempo_recuperacion_medio_h: float | None
    temp_suelo_min: float | None
    temp_suelo_max: float | None
    temp_aire_min: float | None
    temp_aire_max: float | None
    tasa_secado_pct_h: float | None
    created_at: datetime

    model_config = {"from_attributes": True}
