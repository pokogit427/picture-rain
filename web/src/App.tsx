import { useEffect, useState } from "react";
import { getHealth, getPhotos, type PhotoSummary } from "./api";
import "./styles.css";

type LoadState = "loading" | "ready" | "error";

function App() {
  const [healthState, setHealthState] = useState<LoadState>("loading");
  const [photoState, setPhotoState] = useState<LoadState>("loading");
  const [photos, setPhotos] = useState<PhotoSummary[]>([]);

  useEffect(() => {
    let active = true;

    Promise.all([getHealth(), getPhotos()])
      .then(([, loadedPhotos]) => {
        if (!active) return;
        setPhotos(loadedPhotos);
        setHealthState("ready");
        setPhotoState("ready");
      })
      .catch(() => {
        if (!active) return;
        setHealthState("error");
        setPhotoState("error");
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">PICTURE RAIN</p>
          <h1>둘만의 사진 놀이터</h1>
        </div>
        <span className="stage-badge">D01 · 기반 화면</span>
      </header>

      <main className="dashboard">
        <section className="welcome-card">
          <div>
            <p className="eyebrow">오늘의 연결</p>
            <h2>사진을 보내고, 함께 완성해요.</h2>
            <p className="muted">
              현재는 웹 화면과 기존 API 연결을 확인하는 개발 기반입니다.
              연결·편집·동시 공개 기능은 다음 단계에서 추가됩니다.
            </p>
          </div>
          <div className="rain-orb" aria-hidden="true">✦</div>
        </section>

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
          <article className="panel connections-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">PRIVATE CIRCLE</p>
                <h2>연결된 상대</h2>
              </div>
              <button type="button" disabled title="D03에서 추가됩니다">
                + 연결하기
              </button>
            </div>
            <div className="empty-state">
              <span className="empty-icon">☁</span>
              <h3>아직 연결된 상대가 없어요</h3>
              <p>초대 코드로 소중한 사람을 연결하는 기능이 준비 중입니다.</p>
            </div>
          </article>

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

function StatusMessage({ state, ready }: { state: LoadState; ready: string }) {
  if (state === "loading") return <p className="status loading">확인 중…</p>;
  if (state === "error") return <p className="status error">연결 확인 필요</p>;
  return <p className="status ready">{ready}</p>;
}

export default App;
