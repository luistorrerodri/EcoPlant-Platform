import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlantType(Base):
    __tablename__ = "plant_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Slug estable para referenciar el tipo desde fuera de la BD (semillas,
    # futuras migraciones de datos) sin depender del UUID generado.
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))

    # Valores por defecto que se copian a devices.* al elegir el tipo desde
    # la app - no se leen en caliente desde aqui en el ciclo de riego.
    default_humedad_min: Mapped[int] = mapped_column(Integer)
    default_humedad_max: Mapped[int] = mapped_column(Integer)
    default_hora_inicio: Mapped[int] = mapped_column(Integer)
    default_hora_fin: Mapped[int] = mapped_column(Integer)
    default_duracion_riego_ms: Mapped[int] = mapped_column(Integer)

    devices: Mapped[list["Device"]] = relationship(back_populates="plant_type")
