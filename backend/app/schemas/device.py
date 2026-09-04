import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Environment = Literal["interior", "exterior"]


class DeviceSeedRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    name: str | None = None


class DeviceSeedResponse(BaseModel):
    device_id: str
    claim_code: str  # en claro, solo se devuelve aquí, una vez


class DeviceClaimRequest(BaseModel):
    device_id: str
    claim_code: str
    location_id: uuid.UUID


class DeviceUpdate(BaseModel):
    name: str | None = None
    location_id: uuid.UUID | None = None
    plant_type_id: uuid.UUID | None = None
    humedad_min: int | None = Field(default=None, ge=0, le=100)
    hora_inicio: int | None = Field(default=None, ge=0, le=23)
    hora_fin: int | None = Field(default=None, ge=0, le=23)
    environment: Environment | None = None


class DeviceOut(BaseModel):
    device_id: str
    name: str | None
    location_id: uuid.UUID | None
    plant_type_id: uuid.UUID | None
    humedad_min: int
    hora_inicio: int
    hora_fin: int
    duracion_riego_ms: int
    environment: Environment | None
    claimed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReadingPoint(BaseModel):
    time: datetime
    field: str
    value: float


class ReadingsOut(BaseModel):
    device_id: str
    latest_estado: str | None
    points: list[ReadingPoint]
