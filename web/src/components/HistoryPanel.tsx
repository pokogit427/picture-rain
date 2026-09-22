import { useEffect, useState } from "react";
import { ApiError, deleteHistory, getAssetUrl, getConnections, getHistory, getTrash, restoreHistory, type HistoryItem, type HistoryTrashItem } from "../api";

export function HistoryPanel() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [trash, setTrash] = useState<HistoryTrashItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showTrash, setShowTrash] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getConnections()
      .then(async (connections) => {
        const [historyGroups, trashGroups] = await Promise.all([
          Promise.all(connections.map((connection) => getHistory(connection.id))),
          Promise.all(connections.map((connection) => getTrash(connection.id))),
        ]);
        return { historyGroups, trashGroups };
      })
      .then(({ historyGroups, trashGroups }) => {
        if (!active) return;
        setItems(historyGroups.flat());
        setTrash(trashGroups.flat());
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : "이력을 불러오지 못했어요.");
      });
    return () => {
      active = false;
    };
  }, []);

  function toggleSelected(entryId: string) {
    setSelectedIds((current) => current.includes(entryId) ? current.filter((id) => id !== entryId) : [...current, entryId]);
  }

  async function deleteSelected() {
    if (selectedIds.length === 0) return;
    setBusy(true);
    try {
      const selected = items.filter((item) => selectedIds.includes(item.entry_id));
      const groups = new Map<string, string[]>();
      for (const item of selected) groups.set(item.connection_id, [...(groups.get(item.connection_id) ?? []), item.entry_id]);
      await Promise.all([...groups.entries()].map(([connectionId, entryIds]) => deleteHistory(connectionId, entryIds)));
      setItems((current) => current.filter((item) => !selectedIds.includes(item.entry_id)));
      setSelectedIds([]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "이력을 휴지통으로 옮기지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  async function restore(item: HistoryTrashItem) {
    setBusy(true);
    try {
      const restored = await restoreHistory(item.connection_id, item.entry_id);
      setTrash((current) => current.filter((candidate) => candidate.entry_id !== item.entry_id));
      setItems((current) => [restored, ...current]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "이력을 복원하지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="panel history-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">HISTORY</p>
          <h2>완성한 이력</h2>
        </div>
        <div className="history-actions">
          <span className="count-pill">{showTrash ? trash.length : items.length}</span>
          <button className="tool-button" onClick={() => setShowTrash((value) => !value)} type="button">{showTrash ? "목록 보기" : `휴지통 ${trash.length}`}</button>
        </div>
      </div>
      {error ? (
        <p className="auth-error">{error}</p>
      ) : showTrash && trash.length === 0 ? (
        <div className="empty-state compact"><span className="empty-icon">♧</span><p>휴지통이 비어 있습니다.</p></div>
      ) : !showTrash && items.length === 0 ? (
        <div className="empty-state compact">
          <span className="empty-icon">↺</span>
          <p>양쪽이 완성한 사진 이력이 여기에 표시됩니다.</p>
        </div>
      ) : (
        <div className="history-list">
          {!showTrash && selectedIds.length > 0 && <button className="tool-button danger-button" disabled={busy} onClick={() => void deleteSelected()} type="button">선택 항목 휴지통으로 이동 ({selectedIds.length})</button>}
          {(showTrash ? trash : items).map((item) => (
            <article className="history-card" key={item.entry_id}>
              {!showTrash && <input aria-label="이력 선택" checked={selectedIds.includes(item.entry_id)} onChange={() => toggleSelected(item.entry_id)} type="checkbox" />}
              <img alt={item.is_mine ? "내가 수정한 결과" : "상대가 수정한 결과"} src={getAssetUrl(item.url)} />
              <div>
                <strong>{item.is_mine ? "내 수정본" : "상대 수정본"}</strong>
                <small>{showTrash ? `${new Date((item as HistoryTrashItem).purge_at).toLocaleDateString()}까지 복원 가능` : `${new Date(item.revealed_at).toLocaleString()} · ${item.width} × ${item.height}`}</small>
              </div>
              {showTrash && <button className="tool-button" disabled={busy} onClick={() => void restore(item as HistoryTrashItem)} type="button">복원</button>}
            </article>
          ))}
        </div>
      )}
    </article>
  );
}
