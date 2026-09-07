import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WateringEvent(Base):
    __tablename__ = "watering_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(100), ForeignKey("devices.device_id"))

    # Timestamp y duracion tal cual los reporta el propio firmware en el
    # evento "riego_completado" (ver ack["timestamp"]/ack["duracion_ms"]
    # en macetero_produccion_6.ino) - no la hora en la que el backend
    # recibe el mensaje MQTT, que puede llegar con un pequeño retraso.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship(back_populates="watering_events")
