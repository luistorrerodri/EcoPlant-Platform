import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    # El device_id es la clave natural: es literalmente el segmento del
    # topic MQTT (maceteros/{device_id}/...) y el CN del certificado
    # mTLS del dispositivo. No hace falta una clave artificial encima.
    device_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT")
    )

    # Tipo de planta asignado (opcional): solo rellena valores por defecto
    # al elegirlo desde la app, no se lee en el ciclo de riego. Si se borra
    # el tipo, el dispositivo conserva sus umbrales tal cual estan.
    plant_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plant_types.id", ondelete="SET NULL")
    )

    # Configuracion de riego, migrada desde el contexto global de Node-RED
    # (era la unica fuente de verdad hasta ahora). Los server_default de
    # aqui son EXACTAMENTE los que macetero01 tiene hoy en produccion, para
    # que anadir estas columnas no cambie ni un bit del riego automatico.
    humedad_min: Mapped[int] = mapped_column(Integer, server_default="36")
    hora_inicio: Mapped[int] = mapped_column(Integer, server_default="8")
    hora_fin: Mapped[int] = mapped_column(Integer, server_default="21")
    duracion_riego_ms: Mapped[int] = mapped_column(Integer, server_default="9000")

    # "interior" | "exterior" | NULL (sin especificar). No cambia nada del
    # ciclo de riego por si sola - es la bandera que decidira mas adelante
    # si se consulta la API meteorologica antes de regar en automatico.
    environment: Mapped[str | None] = mapped_column(String(20))

    # Hash del codigo de reclamacion (bcrypt, igual que una contraseña).
    # Se pone a NULL en cuanto se reclama - de un solo uso. Para volver
    # a reclamar un dispositivo desenganchado hace falta que un admin
    # rote un codigo nuevo.
    claim_code_hash: Mapped[str | None] = mapped_column(String(255))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["Location | None"] = relationship(back_populates="devices")
    plant_type: Mapped["PlantType | None"] = relationship(back_populates="devices")
    watering_events: Mapped[list["WateringEvent"]] = relationship(back_populates="device")
    health_summaries: Mapped[list["HealthSummary"]] = relationship(back_populates="device")
