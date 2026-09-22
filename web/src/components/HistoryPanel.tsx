import { useEffect, useState } from "react";
import { ApiError, getAssetUrl, getConnections, getHistory, type HistoryItem } from "../api";

export function HistoryPanel() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getConnections()
      .then((connections) => Promise.all(connections.map((connection) => getHistory(connection.id))))
      .then((groups) => {
        if (!active) return;
        setItems(groups.flat());
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "이력을 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <article className="panel history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HISTORY</p>
          <h2>완성한 이력</h2>
        </div>
        <span className="count-pill">{items.length}</span>
      </div>
      {error ? (
        <p className="auth-error">{error}</p>
      ) : items.length === 0 ? (
        <div className="empty-state compact">
          <span className="empty-icon">↺</span>
          <p>양쪽이 완성한 사진 이력이 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-card" key={item.entry_id}>
              <img alt={item.is_mine ? "내가 수정한 결과" : "상대가 수정한 결과"} src={getAssetUrl(item.url)} />
              <div>
                <strong>{item.is_mine ? "내 수정본" : "상대 수정본"}</strong>
                <small>{new Date(item.revealed_at).toLocaleString()} · {item.width} × {item.height}</small>
              </div>
            </article>
          ))}
        </div>
      )}
    </article>
  );
}
