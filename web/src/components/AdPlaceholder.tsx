import { useEffect, useState } from "react";
import { getAdSlots, type AdSlotSummary } from "../api";

export function AdPlaceholder({ slot }: { slot: string }) {
  const [ad, setAd] = useState<AdSlotSummary | null>(null);

  useEffect(() => {
    let active = true;
    getAdSlots(slot)
      .then((slots) => {
        if (active) setAd(slots.find((item) => item.enabled) ?? null);
      })
      .catch(() => {
        if (active) setAd(null);
      });
    return () => {
      active = false;
    };
  }, [slot]);

  if (!ad) return null;
  return (
    <aside className="ad-placeholder" aria-label={ad.label ?? "광고 영역"}>
      <span>{ad.label}</span>
      <small>외부 콘텐츠를 불러오지 않는 검토용 영역</small>
    </aside>
  );
}
