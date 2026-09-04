from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.plant_type import PlantType
from app.models.user import User
from app.schemas.plant_type import PlantTypeOut

router = APIRouter(prefix="/api/plant-types", tags=["plant-types"])


@router.get("", response_model=list[PlantTypeOut])
def list_plant_types(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PlantType]:
    return db.query(PlantType).order_by(PlantType.name).all()
