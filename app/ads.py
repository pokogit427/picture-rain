import os
from dataclasses import dataclass


DEFAULT_AD_SLOTS = ("dashboard", "history")


@dataclass(frozen=True)
class AdSlot:
    slot: str
    mode: str
    enabled: bool
    label: str | None
    click_url: str | None


def current_ad_mode() -> str:
    """Return the explicitly supported local ad mode.

    Ads are disabled unless a deployment opts into the non-network mock mode.
    Unknown values fail closed to avoid accidentally enabling a paid provider.
    """
    requested = os.getenv("PICTURE_RAIN_ADS_MODE", "OFF").strip().upper()
    return "MOCK" if requested == "MOCK" else "OFF"


def get_ad_slots(slot: str | None = None) -> list[AdSlot]:
    requested_slots = (slot,) if slot else DEFAULT_AD_SLOTS[:1]
    allowed_slots = [name for name in requested_slots if name in DEFAULT_AD_SLOTS]
    if not allowed_slots:
        return []

    mode = current_ad_mode()
    enabled = mode == "MOCK"
    return [
        AdSlot(
            slot=name,
            mode=mode,
            enabled=enabled,
            label="검토용 광고 영역" if enabled else None,
            click_url=None,
        )
        for name in allowed_slots
    ]
