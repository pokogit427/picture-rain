import { useEffect, useState } from "react";
import {
  ApiError,
  getHealth,
  getMe,
  getPhotos,
  logout,
  type PhotoSummary,
  type UserSummary,
} from "./api";
import { AuthPanel } from "./components/AuthPanel";
import { AdPlaceholder } from "./components/AdPlaceholder";
import { ConnectionPanel } from "./components/ConnectionPanel";
import { InboxPanel } from "./components/InboxPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import "./styles.css";

type LoadState = "loading" | "ready" | "error";
type SessionState = "checking" | "anonymous" | "authenticated" | "error";

function App() {
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [user, setUser] = useState<UserSummary | null>(null);
  const [healthState, setHealthState] = useState<LoadState>("loading");
  const [photoState, setPhotoState] = useState<LoadState>("loading");
  const [photos, setPhotos] = useState<PhotoSummary[]>([]);

  useEffect(() => {
    let active = true;
    getMe()
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
        setSessionState("authenticated");
        void loadDashboard(setHealthState, setPhotoState, setPhotos);
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) {
          setSessionState("anonymous");
        } else {
          setSessionState("error");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleAuthenticated(currentUser: UserSummary) {
    setUser(currentUser);
    setSessionState("authenticated");
    await loadDashboard(setHealthState, setPhotoState, setPhotos);
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setPhotos([]);
    setSessionState("anonymous");
  }

  if (sessionState === "checking") {
    return <LoadingScreen message="안전한 세션을 확인하고 있어요…" />;
  }
  if (sessionState === "anonymous") {
    return <AuthPanel onAuthenticated={handleAuthenticated} />;
  }
  if (sessionState === "error" || user === null) {
    return <LoadingScreen message="서비스 연결을 확인해주세요." error />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">PICTURE RAIN</p>
          <h1>둘만의 사진 놀이터</h1>
        </div>
        <div className="account-actions">
          <span className="user-pill">@{user.login_identifier}</span>
          <button className="logout-button" onClick={handleLogout} type="button">
            로그아웃
          </button>
          <span className="stage-badge">D06 · 연결 준비</span>
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome-card">
          <div>
            <p className="eyebrow">오늘의 연결</p>
            <h2>사진을 보내고, 함께 완성해요.</h2>
            <p className="muted">
              초대 코드로 연결된 상대를 관리하고 사진 교환을 준비하는 화면입니다.
              편집·동시 공개 기능은 다음 단계에서 이어집니다.
            </p>
          </div>
          <div className="rain-orb" aria-hidden="true">✦</div>
        </section>

        <AdPlaceholder slot="dashboard" />

        <section className="status-grid" aria-label="개발 상태">
          <article className="panel status-panel">
            <div className="panel-heading">
              <span className="icon-chip">↗</span>
              <div>
                <p className="eyebrow">SYSTEM</p>
                <h3>API 연결</h3>
              </div>
            </div>
            <StatusMessage state={healthState} ready="정상 연결됨" />
          </article>

          <article className="panel status-panel">
            <div className="panel-heading">
              <span className="icon-chip">◎</span>
              <div>
                <p className="eyebrow">STORAGE</p>
                <h3>사진 기록</h3>
              </div>
            </div>
            <StatusMessage
              state={photoState}
              ready={`${photos.length}개의 사진`}
            />
          </article>
        </section>

        <section className="content-grid">
          <ConnectionPanel />

          <InboxPanel />

          <HistoryPanel />

          <article className="panel photos-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">PHOTO LOG</p>
                <h2>최근 사진</h2>
              </div>
              <span className="count-pill">{photos.length}</span>
            </div>
            {photoState === "ready" && photos.length === 0 ? (
              <div className="empty-state compact">
                <span className="empty-icon">✧</span>
                <p>아직 저장된 사진이 없습니다.</p>
              </div>
            ) : (
              <ul className="photo-list">
                {photos.map((photo) => (
                  <li key={photo.id}>
                    <span>{photo.filename ?? "이름 없는 사진"}</span>
                    <small>{photo.width} × {photo.height}</small>
                  </li>
                ))}
              </ul>
            )}
          </article>
        </section>
      </main>

      <footer className="footer-note">
        <span>저비용·무료 우선 개발</span>
        <span>기능 구현 단계 전용 개발 화면</span>
      </footer>
    </div>
  );
}

async function loadDashboard(
  setHealthState: (state: LoadState) => void,
  setPhotoState: (state: LoadState) => void,
  setPhotos: (photos: PhotoSummary[]) => void,
) {
  try {
    const [, loadedPhotos] = await Promise.all([getHealth(), getPhotos()]);
    setPhotos(loadedPhotos);
    setHealthState("ready");
    setPhotoState("ready");
  } catch {
    setHealthState("error");
    setPhotoState("error");
  }
}

function LoadingScreen({ message, error = false }: { message: string; error?: boolean }) {
  return (
    <main className="auth-layout">
      <section className="auth-card loading-card">
        <p className="eyebrow">PICTURE RAIN</p>
        <h1>{error ? "연결이 필요해요" : "잠시만요"}</h1>
        <p className={error ? "auth-error" : "auth-description"}>{message}</p>
      </section>
    </main>
  );
}

function StatusMessage({ state, ready }: { state: LoadState; ready: string }) {
  if (state === "loading") return <p className="status loading">확인 중…</p>;
  if (state === "error") return <p className="status error">연결 확인 필요</p>;
  return <p className="status ready">{ready}</p>;
}

export default App;
