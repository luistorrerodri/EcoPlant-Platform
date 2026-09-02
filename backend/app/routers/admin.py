from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceSeedRequest, DeviceSeedResponse
from app.security import generate_claim_code, hash_claim_code

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/devices/seed", response_model=DeviceSeedResponse, status_code=status.HTTP_201_CREATED)
def seed_device(
    data: DeviceSeedRequest,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> DeviceSeedResponse:
    if db.get(Device, data.device_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese device_id ya existe")

    claim_code = generate_claim_code()
    device = Device(
        device_id=data.device_id,
        name=data.name,
        claim_code_hash=hash_claim_code(claim_code),
    )
    db.add(device)
    db.commit()
    # El codigo en claro solo existe en este momento - no se guarda en
    # ningun sitio, solo su hash. Apuntarlo ahora (sticker fisico,
    # mensaje al usuario) o se pierde.
    return DeviceSeedResponse(device_id=device.device_id, claim_code=claim_code)


@router.post("/devices/{device_id}/rotate-claim-code", response_model=DeviceSeedResponse)
def rotate_claim_code(
    device_id: str,
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> DeviceSeedResponse:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado")

    claim_code = generate_claim_code()
    device.claim_code_hash = hash_claim_code(claim_code)
    device.location_id = None
    device.claimed_at = None
    db.commit()
    return DeviceSeedResponse(device_id=device.device_id, claim_code=claim_code)
