import { afterEach, describe, expect, it, vi } from "vitest";
import { getHealth, getPhotos } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("API client", () => {
  it("loads health information through the local API base path", async () => {
    const response = { status: "ok", database: "ok", timestamp: "now" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    );

    await expect(getHealth()).resolves.toEqual(response);
    expect(fetch).toHaveBeenCalledWith("/api/health");
  });

  it("returns the photo list from the existing API", async () => {
    const photos = [
      {
        id: "photo-1",
        filename: "sample.jpg",
        content_type: "image/jpeg",
        size: 123,
        width: 640,
        height: 480,
        created_at: null,
        url: "/photos/photo-1",
      },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(photos), { status: 200 }),
    );

    await expect(getPhotos()).resolves.toEqual(photos);
    expect(fetch).toHaveBeenCalledWith("/api/photos");
  });

  it("exposes a useful error when the API rejects a request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("unavailable", { status: 503 }),
    );

    await expect(getHealth()).rejects.toThrow("API 요청 실패 (503)");
  });
});
