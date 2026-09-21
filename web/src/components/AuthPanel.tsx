import { FormEvent, useState } from "react";
import {
  ApiError,
  login,
  register,
  type UserSummary,
} from "../api";

type AuthMode = "login" | "register";

interface AuthPanelProps {
  onAuthenticated: (user: UserSummary) => void;
}

export function AuthPanel({ onAuthenticated }: AuthPanelProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegistering = mode === "register";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);
    try {
      const user = isRegistering
        ? await register({ login_identifier: loginIdentifier, password })
        : await login({ login_identifier: loginIdentifier, password });
      onAuthenticated(user);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("잠시 후 다시 시도해주세요.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setErrorMessage("");
  }

  return (
    <main className="auth-layout">
      <section className="auth-card">
        <p className="eyebrow">PICTURE RAIN</p>
        <h1>{isRegistering ? "우리만의 사진 공간 만들기" : "다시 만나요"}</h1>
        <p className="auth-description">
          사용자명과 비밀번호로 로그인하고, 초대 코드로 소중한 사람과 연결하세요.
        </p>

        <div className="auth-tabs" role="tablist" aria-label="인증 방식">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => changeMode("login")}
          >
            로그인
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => changeMode("register")}
          >
            회원가입
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            사용자명
            <input
              autoComplete="username"
              maxLength={32}
              minLength={3}
              onChange={(event) => setLoginIdentifier(event.target.value)}
              pattern="[A-Za-z0-9_]{3,32}"
              placeholder="영문, 숫자, 밑줄 3~32자"
              required
              value={loginIdentifier}
            />
          </label>
          <label>
            비밀번호
            <input
              autoComplete={isRegistering ? "new-password" : "current-password"}
              maxLength={128}
              minLength={isRegistering ? 12 : 1}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={isRegistering ? "12자 이상" : "비밀번호 입력"}
              required
              type="password"
              value={password}
            />
          </label>
          {errorMessage && <p className="auth-error" role="alert">{errorMessage}</p>}
          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "처리 중…" : isRegistering ? "시작하기" : "로그인"}
          </button>
        </form>

        <p className="auth-note">초기 버전에서는 비밀번호 분실 복구를 지원하지 않습니다.</p>
      </section>
    </main>
  );
}
