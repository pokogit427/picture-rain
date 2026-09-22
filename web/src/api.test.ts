import { afterEach, describe, expect, it, vi } from "vitest";
import { getHealth, getMe, getPhotos, saveDraft } from "./api";

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
    expect(fetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("loads the authenticated user through the session cookie", async () => {
    const user = {
      id: "user-1",
      login_identifier: "sample_user",
      status: "ACTIVE",
      created_at: "now",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), { status: 200 }),
    );

    await expect(getMe()).resolves.toEqual(user);
    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "include" }),
    );
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
    expect(fetch).toHaveBeenCalledWith(
      "/api/photos",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("exposes a useful error when the API rejects a request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required." }), {
        status: 401,
      }),
    );

    await expect(getMe()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Authentication required.",
    });
  });

  it("sends drafts as multipart data without overriding the browser boundary", async () => {
    const draft = {
      id: "draft-1",
      round_id: "round-1",
      version: 1,
      document: { strokes: [], layers: [] },
      preview: null,
      updated_at: "now",
      expires_at: "later",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(draft), { status: 200 }),
    );

    await expect(saveDraft("round-1", JSON.stringify(draft.document), new Blob(["png"], { type: "image/png" }))).resolves.toEqual(draft);
    const request = fetchMock.mock.calls[0]?.[1];
    expect(request?.headers).not.toEqual(expect.objectContaining({ "Content-Type": "application/json" }));
    expect(request?.body).toBeInstanceOf(FormData);
  });
});
