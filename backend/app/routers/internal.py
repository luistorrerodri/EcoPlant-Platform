from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_internal_token
from app.models.device import Device
from app.schemas.internal import DeviceConfigOut
from app.services import weather_client

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
    result: dict[str, dict] = {}
    for d in devices:
        # lluviaPrevista solo se calcula (y solo puede dar True) para
        # dispositivos exteriores con coordenadas - en cualquier otro
        # caso queda en False, que es exactamente el comportamiento de
        # antes de que existiera este campo (fail-open por diseño).
        lluvia_prevista = False
        if d.environment == "exterior" and d.location is not None:
            if d.location.latitude is not None and d.location.longitude is not None:
                if weather_client.get_rain_forecast(d.location.latitude, d.location.longitude):
                    lluvia_prevista = True
        result[d.device_id] = {
            "humedadMin": d.humedad_min,
            "humedadMax": d.humedad_max,
            "horaInicio": d.hora_inicio,
            "horaFin": d.hora_fin,
            "duracionRiegoMs": d.duracion_riego_ms,
            "lluviaPrevista": lluvia_prevista,
        }
    return result
