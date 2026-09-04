from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_internal_token
from app.models.device import Device
from app.schemas.internal import DeviceConfigOut

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.get(
    "/device-configs",
    response_model=dict[str, DeviceConfigOut],
    dependencies=[Depends(verify_internal_token)],
)
def get_device_configs(db: Session = Depends(get_db)) -> dict[str, dict]:
    # Solo dispositivos reclamados: uno sin reclamar no tiene dueño ni
    # sentido de regarlo. La forma de la respuesta sustituye tal cual el
    # config_maceteros que Node-RED ya mantiene en su contexto global.
    devices = db.query(Device).filter(Device.claimed_at.isnot(None)).all()
    return {
        d.device_id: {
            "humedadMin": d.humedad_min,
            "horaInicio": d.hora_inicio,
            "horaFin": d.hora_fin,
            "duracionRiegoMs": d.duracion_riego_ms,
        }
        for d in devices
    }
