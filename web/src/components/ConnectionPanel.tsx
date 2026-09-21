import { useEffect, useState } from "react";
import {
  acceptInvite,
  ApiError,
  getConnections,
  getCurrentInvite,
  issueInvite,
  type ConnectionSummary,
  type InviteSummary,
} from "../api";

export function ConnectionPanel() {
  const [connections, setConnections] = useState<ConnectionSummary[]>([]);
  const [invite, setInvite] = useState<InviteSummary | null>(null);
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getConnections(), getCurrentInvite()])
      .then(([loadedConnections, loadedInvite]) => {
        if (!active) return;
        setConnections(loadedConnections);
        setInvite(loadedInvite);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? reason.message : "연결 정보를 불러오지 못했어요.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function refreshInvite() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setInvite(await issueInvite());
      setMessage("새 초대 코드를 발급했어요.");
    } catch (reason: unknown) {
      setError(reason instanceof ApiError ? reason.message : "초대 코드를 발급하지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    if (!/^\d{4}$/.test(code)) {
      setError("초대 코드 4자리를 입력해주세요.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const connection = await acceptInvite(code);
      setConnections((current) => [connection, ...current]);
      setCode("");
      setMessage("새 연결을 만들었어요.");
      setInvite(await issueInvite());
    } catch (reason: unknown) {
      setError(reason instanceof ApiError ? reason.message : "상대 연결에 실패했어요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="panel connections-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">PRIVATE CIRCLE</p>
          <h2>연결된 상대</h2>
        </div>
        <span className="count-pill">{connections.length}</span>
      </div>

      <div className="invite-card">
        <div>
          <p className="eyebrow">MY INVITE CODE</p>
          <strong className="invite-code">{invite?.code ?? "----"}</strong>
          <p className="invite-help">5분 동안 유효하며 새로 발급해도 기존 연결은 유지됩니다.</p>
        </div>
        <button className="secondary-button" disabled={busy || loading} onClick={refreshInvite} type="button">
          새 코드
        </button>
      </div>

      <div className="connect-form">
        <label htmlFor="invite-code">상대의 초대 코드</label>
        <div className="connect-controls">
          <input
            id="invite-code"
            inputMode="numeric"
            maxLength={4}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            placeholder="숫자 4자리"
            value={code}
          />
          <button className="primary-button compact-button" disabled={busy || loading} onClick={connect} type="button">
            연결
          </button>
        </div>
      </div>

      {message && <p className="inline-message success-message">{message}</p>}
      {error && <p className="inline-message auth-error">{error}</p>}

      {connections.length === 0 ? (
        <div className="empty-state connection-empty">
          <span className="empty-icon">☁</span>
          <h3>아직 연결된 상대가 없어요</h3>
          <p>내 코드를 공유하거나 상대의 코드를 입력해 연결을 시작하세요.</p>
        </div>
      ) : (
        <ul className="connection-list">
          {connections.map((connection) => (
            <li key={connection.id}>
              <span className="connection-avatar">♡</span>
              <span>
                <strong>상대 {connection.partner_user_id.slice(0, 8)}</strong>
                <small>연결됨 · 사진 교환 준비 중</small>
              </span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
