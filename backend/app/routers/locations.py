import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.location import Location
from app.models.user import User
from app.schemas.location import LocationCreate, LocationOut, LocationUpdate

router = APIRouter(prefix="/api/locations", tags=["locations"])


def _get_owned_location_or_404(location_id: uuid.UUID, user: User, db: Session) -> Location:
    # 404, no 403: que una ubicacion exista pero sea de otro usuario no
    # debe distinguirse de que no exista, para no filtrar informacion.
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.owner_id == user.id)
        .first()
    )
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ubicación no encontrada")
    return location


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    data: LocationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Location:
    location = Location(owner_id=user.id, name=data.name, description=data.description)
    db.add(location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ya tienes una ubicación con ese nombre"
        )
    db.refresh(location)
    return location


@router.get("", response_model=list[LocationOut])
def list_locations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Location]:
    return db.query(Location).filter(Location.owner_id == user.id).order_by(Location.created_at).all()


@router.get("/{location_id}", response_model=LocationOut)
def get_location(
    location_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Location:
    return _get_owned_location_or_404(location_id, user, db)


@router.patch("/{location_id}", response_model=LocationOut)
def update_location(
    location_id: uuid.UUID,
    data: LocationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Location:
    location = _get_owned_location_or_404(location_id, user, db)
    if data.name is not None:
        location.name = data.name
    if data.description is not None:
        location.description = data.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ya tienes una ubicación con ese nombre"
        )
    db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    location = _get_owned_location_or_404(location_id, user, db)
    db.delete(location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ubicación todavía tiene dispositivos enganchados; desengánchalos primero",
        )
