import { afterEach, describe, expect, it } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { NetworkStatus } from "./NetworkStatus";

let root: Root | undefined;

afterEach(() => {
  act(() => root?.unmount());
  document.body.innerHTML = "";
  Object.defineProperty(window.navigator, "onLine", { configurable: true, value: true });
});

describe("NetworkStatus", () => {
  it("shows a recovery message while the browser is offline", async () => {
    Object.defineProperty(window.navigator, "onLine", { configurable: true, value: false });
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkStatus />);
    });

    expect(container.textContent).toContain("인터넷 연결이 끊겼어요");
  });

  it("removes the message after the browser comes back online", async () => {
    Object.defineProperty(window.navigator, "onLine", { configurable: true, value: false });
    const container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<NetworkStatus />);
    });
    await act(async () => {
      window.dispatchEvent(new Event("online"));
    });

    expect(container.textContent).toBe("");
  });
});
