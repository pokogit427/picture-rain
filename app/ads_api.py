from fastapi import APIRouter, Depends, Query

from app.ads import get_ad_slots
from app.auth import get_current_user
from app.models import User
from app.schemas import AdSlotResponse


router = APIRouter(prefix="/ads", tags=["ads"])


@router.get("/slots", response_model=list[AdSlotResponse])
def read_ad_slots(
    slot: str | None = Query(default=None, min_length=1, max_length=32),
    _user: User = Depends(get_current_user),
) -> list[AdSlotResponse]:
    return [AdSlotResponse.model_validate(item) for item in get_ad_slots(slot)]
