from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.auth import get_current_user
from app.db import get_db
from app.entitlement import current_policy
from app.models import User
from app.pairing import find_member_connection
from app.schemas import EntitlementResponse, UsageResponse
from app.usage import get_usage_summary
from sqlalchemy.orm import Session

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


@router.get("/connections/{connection_id}/usage", response_model=UsageResponse)
def get_connection_usage(
    connection_id: str = Path(min_length=32, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsageResponse:
    if find_member_connection(db, connection_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    usage = get_usage_summary(db, user_id=user.id, connection_id=connection_id)
    return UsageResponse(
        usage_date=usage.usage_date,
        connection_used=usage.connection_used,
        connection_limit=usage.connection_limit,
        account_used=usage.account_used,
        account_limit=usage.account_limit,
    )
