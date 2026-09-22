"""Feature-policy boundary for the currently free-only product."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanPolicy:
    code: str
    status: str
    billing_enabled: bool
    daily_rounds_per_connection: int
    total_rounds_per_account: int


FREE_POLICY = PlanPolicy(
    code="FREE",
    status="PREVIEW",
    billing_enabled=False,
    daily_rounds_per_connection=3,
    total_rounds_per_account=30,
)


def current_policy() -> PlanPolicy:
    """Return only a known policy; unknown env values never become unlimited."""
    requested = os.getenv("PICTURE_RAIN_PLAN", "FREE").upper()
    if requested != FREE_POLICY.code:
        return FREE_POLICY
    return FREE_POLICY
