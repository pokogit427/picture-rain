import { useEffect, useState } from "react";
import {
  ApiError,
  getAssetUrl,
  getConnections,
  getInbox,
  type InboxItem,
} from "../api";

export function InboxPanel() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getConnections()
      .then((connections) => Promise.all(connections.map((connection) => getInbox(connection.id))))
      .then((groups) => {
        if (!active) return;
        const loaded = groups.flat();
        setItems(loaded);
        setSelected(loaded[0] ?? null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "받은 사진을 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <article className="panel inbox-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">INBOX</p>
          <h2>받은 사진</h2>
        </div>
        <span className="count-pill">{items.length}</span>
      </div>
      {error ? (
        <p className="auth-error">{error}</p>
      ) : items.length === 0 ? (
        <div className="empty-state compact">
          <span className="empty-icon">✧</span>
          <p>상대가 보낸 사진이 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="inbox-content">
          <div className="inbox-tabs">
            {items.map((item) => (
              <button
                className={selected?.round_id === item.round_id ? "active" : ""}
                key={item.round_id}
                onClick={() => setSelected(item)}
                type="button"
              >
                교환 {item.round_id.slice(0, 6)}
              </button>
            ))}
          </div>
          {selected && (
            <div className="received-photo-card">
              <img
                alt="상대가 보낸 편집 대상"
                src={getAssetUrl(selected.input.url)}
              />
              <div>
                <strong>편집할 사진</strong>
                <small>{selected.input.width} × {selected.input.height} · 다음 단계에서 편집</small>
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
