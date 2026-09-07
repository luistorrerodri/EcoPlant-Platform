from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.device import Device
from app.models.health_summary import HealthSummary
from app.models.location import Location
from app.models.plant_type import PlantType
from app.models.user import User
from app.schemas.device import DeviceClaimRequest, DeviceOut, DeviceUpdate, ReadingsOut
from app.schemas.health import HealthSummaryOut
from app.security import verify_claim_code
from app.services import health_analysis, influx_client, mqtt_client

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _get_owned_device_or_404(device_id: str, user: User, db: Session) -> Device:
    device = (
        db.query(Device)
        .join(Location, Device.location_id == Location.id)
        .filter(Device.device_id == device_id, Location.owner_id == user.id)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado")
    return device


@router.post("/claim", response_model=DeviceOut, status_code=status.HTTP_200_OK)
def claim_device(
    data: DeviceClaimRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Device:
    device = db.get(Device, data.device_id)
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="device_id o código incorrectos")
    if device is None or device.claim_code_hash is None:
        raise invalid
    if not verify_claim_code(data.claim_code, device.claim_code_hash):
        raise invalid

    location = (
        db.query(Location)
        .filter(Location.id == data.location_id, Location.owner_id == user.id)
        .first()
    )
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicación no encontrada")

    device.location_id = location.id
    device.claimed_at = datetime.now(timezone.utc)
    device.claim_code_hash = None  # de un solo uso
    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=list[DeviceOut])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Device]:
    return (
        db.query(Device)
        .join(Location, Device.location_id == Location.id)
        .filter(Location.owner_id == user.id)
        .order_by(Device.claimed_at)
        .all()
    )


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Device:
    return _get_owned_device_or_404(device_id, user, db)


@router.patch("/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: str,
    data: DeviceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Device:
    device = _get_owned_device_or_404(device_id, user, db)
    if data.name is not None:
        device.name = data.name
    if data.location_id is not None:
        new_location = (
            db.query(Location)
            .filter(Location.id == data.location_id, Location.owner_id == user.id)
            .first()
        )
        if new_location is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicación no encontrada")
        device.location_id = new_location.id
    if data.plant_type_id is not None:
        plant_type = db.get(PlantType, data.plant_type_id)
        if plant_type is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de planta no encontrado")
        device.plant_type_id = plant_type.id
    if data.humedad_min is not None:
        device.humedad_min = data.humedad_min
    if data.hora_inicio is not None:
        device.hora_inicio = data.hora_inicio
    if data.hora_fin is not None:
        device.hora_fin = data.hora_fin
    if data.environment is not None:
        device.environment = data.environment
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}/readings", response_model=ReadingsOut)
def get_readings(
    device_id: str,
    hours: int = 24,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _get_owned_device_or_404(device_id, user, db)  # comprobacion de propiedad
    return influx_client.get_readings(device_id, hours)


@router.post("/{device_id}/water", status_code=status.HTTP_202_ACCEPTED)
def water_device(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    _get_owned_device_or_404(device_id, user, db)  # comprobacion de propiedad
    mqtt_client.publish_water_command(device_id)
    return {"status": "comando de riego enviado"}


@router.get("/{device_id}/health-summary", response_model=HealthSummaryOut)
def get_health_summary(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthSummary:
    _get_owned_device_or_404(device_id, user, db)
    summary = (
        db.query(HealthSummary)
        .filter(HealthSummary.device_id == device_id)
        .order_by(HealthSummary.created_at.desc())
        .first()
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todavía no hay ningún resumen de salud para este dispositivo",
        )
    return summary


@router.post("/{device_id}/health-summary/refresh", response_model=HealthSummaryOut)
def refresh_health_summary(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> HealthSummary:
    device = _get_owned_device_or_404(device_id, user, db)
    result = health_analysis.compute_health_summary(device, db)
    summary = HealthSummary(device_id=device_id, **result.__dict__)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unclaim_device(
    device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    device = _get_owned_device_or_404(device_id, user, db)
    # Desenganchar, no borrar el dispositivo: sigue existiendo en el
    # sistema, solo deja de estar asociado a ningun usuario. Sin un
    # codigo de reclamacion vivo (se consumio al reclamarlo), hace
    # falta que un admin rote uno nuevo para que alguien lo reclame.
    device.location_id = None
    device.claimed_at = None
    db.commit()
