import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HealthSummary(Base):
    __tablename__ = "health_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String(100), ForeignKey("devices.device_id"))

    window_days: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(1000))

    # Metricas individuales, no un blob JSON - mismo estilo que el resto
    # del esquema. Todas nullable: cada una puede faltar por su cuenta
    # (p.ej. sin riegos en la ventana, tiempo_recuperacion_medio_h queda
    # NULL sin que eso invalide el resto).
    pct_tiempo_bajo_minimo: Mapped[float | None] = mapped_column(Float)
    pct_tiempo_saturado: Mapped[float | None] = mapped_column(Float)
    num_riegos: Mapped[int | None] = mapped_column(Integer)
    tiempo_recuperacion_medio_h: Mapped[float | None] = mapped_column(Float)
    temp_suelo_min: Mapped[float | None] = mapped_column(Float)
    temp_suelo_max: Mapped[float | None] = mapped_column(Float)
    temp_aire_min: Mapped[float | None] = mapped_column(Float)
    temp_aire_max: Mapped[float | None] = mapped_column(Float)
    tasa_secado_pct_h: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship(back_populates="health_summaries")
