import { afterEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { act } from "react";
import App from "./App";

let root: Root | undefined;

afterEach(() => {
  act(() => root?.unmount());
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("web shell", () => {
  it("renders the authenticated connection and photo log areas", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      let body: unknown;
      if (url.endsWith("/auth/me")) {
        body = {
          id: "user-1",
          login_identifier: "sample_user",
          status: "ACTIVE",
          created_at: "now",
        };
      } else if (url.endsWith("/health")) {
        body = { status: "ok", database: "ok", timestamp: "now" };
      } else {
        body = [];
      }
      return new Response(JSON.stringify(body), { status: 200 });
    });

    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<App />);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(container.textContent).toContain("연결된 상대");
    expect(container.textContent).toContain("최근 사진");
    expect(container.textContent).toContain("@sample_user");
  });

  it("shows the login form when the session is absent", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required." }), {
        status: 401,
      }),
    );

    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<App />);
      await Promise.resolve();
    });

    expect(container.textContent).toContain("로그인");
    expect(container.textContent).toContain("회원가입");
  });
});
