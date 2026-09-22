from datetime import datetime
from typing import Literal

from pydantic import BaseModel

PhotoVerdict = Literal["bien", "revisar", "preocupante"]


class PhotoDiagnosisOut(BaseModel):
    device_id: str
    verdict: PhotoVerdict
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
