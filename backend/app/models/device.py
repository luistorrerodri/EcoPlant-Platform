import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
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

    # Hash del codigo de reclamacion (bcrypt, igual que una contraseña).
    # Se pone a NULL en cuanto se reclama - de un solo uso. Para volver
    # a reclamar un dispositivo desenganchado hace falta que un admin
    # rote un codigo nuevo.
    claim_code_hash: Mapped[str | None] = mapped_column(String(255))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["Location | None"] = relationship(back_populates="devices")
