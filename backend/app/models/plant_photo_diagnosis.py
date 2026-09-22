from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlantPhotoDiagnosis(Base):
    __tablename__ = "plant_photo_diagnoses"

    # Una fila por dispositivo, no un historico: se sobreescribe con cada
    # foto nueva (device_id como clave primaria, no un id propio con
    # created_at creciente como health_summaries). Antes de sobreescribir,
    # la foto que hay aqui es la que se usa como "foto anterior" para que
    # la IA compare evolucion - ver app/services/plant_vision.py.
    device_id: Mapped[str] = mapped_column(String(100), ForeignKey("devices.device_id"), primary_key=True)

    photo: Mapped[bytes] = mapped_column(LargeBinary)
    photo_content_type: Mapped[str] = mapped_column(String(50))

    # Veredicto propio de esta pieza, deliberadamente distinto del
    # HealthVerdict del resumen estadistico (SECO/revisar_riego/...) - un
    # sintoma visual (plaga, hojas amarillas) no encaja en esas categorias
    # pensadas para umbrales de humedad.
    verdict: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship(back_populates="plant_photo_diagnosis")
