from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.entitlement import current_policy
from app.models import User
from app.schemas import EntitlementResponse

router = APIRouter(tags=["entitlements"])


@router.get("/entitlements", response_model=EntitlementResponse)
def get_entitlements(user: User = Depends(get_current_user)) -> EntitlementResponse:
    policy = current_policy()
    return EntitlementResponse(
        plan_code=policy.code,
        plan_status=policy.status,
        billing_enabled=policy.billing_enabled,
        daily_rounds_per_connection=policy.daily_rounds_per_connection,
        total_rounds_per_account=policy.total_rounds_per_account,
    )
