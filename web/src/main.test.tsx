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
  it("renders the connection and photo log areas", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const body = url.endsWith("/health")
        ? { status: "ok", database: "ok", timestamp: "now" }
        : [];
      return new Response(JSON.stringify(body), { status: 200 });
    });

    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<App />);
      await Promise.resolve();
    });

    expect(container.textContent).toContain("연결된 상대");
    expect(container.textContent).toContain("최근 사진");
    expect(container.textContent).toContain("정상 연결됨");
  });
});
