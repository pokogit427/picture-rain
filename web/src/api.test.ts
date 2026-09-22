import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteHistory, disconnectConnection, getEntitlements, getHealth, getHistory, getMe, getPhotos, getResults, getTrash, getUsage, restoreHistory, saveDraft, submitRound } from "./api";

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

  it("submits a round through the idempotent completion endpoint", async () => {
    const submission = {
      id: "submission-1",
      round_id: "round-1",
      status: "SUBMITTED",
      result: {
        id: "asset-1",
        content_type: "image/png",
        size: 10,
        width: 1,
        height: 1,
        created_at: "now",
        url: "/assets/asset-1/content",
      },
      submitted_at: "now",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(submission), { status: 200 }),
    );

    await expect(submitRound("round-1")).resolves.toEqual(submission);
    expect(fetch).toHaveBeenCalledWith(
      "/api/rounds/round-1/submit",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("loads result visibility from the server-controlled result route", async () => {
    const results = [{
      submission_id: "submission-1",
      is_mine: false,
      visibility: "MOSAIC" as const,
      content_type: "image/png",
      size: 10,
      width: 1,
      height: 1,
      submitted_at: "now",
      url: "/rounds/round-1/results/submission-1/content",
    }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(results), { status: 200 }),
    );

    await expect(getResults("round-1")).resolves.toEqual(results);
    expect(fetch).toHaveBeenCalledWith(
      "/api/rounds/round-1/results",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("loads only result history for a selected connection", async () => {
    const history = [{
      entry_id: "entry-1",
      connection_id: "connection-1",
      round_id: "round-1",
      submission_id: "submission-1",
      is_mine: false,
      content_type: "image/png",
      size: 10,
      width: 1,
      height: 1,
      submitted_at: "now",
      revealed_at: "later",
      url: "/connections/connection-1/history/entry-1/content",
    }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(history), { status: 200 }),
    );

    await expect(getHistory("connection-1")).resolves.toEqual(history);
    expect(fetch).toHaveBeenCalledWith(
      "/api/connections/connection-1/history",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("moves selected history to trash and restores it through explicit endpoints", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(["entry-1"]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ entry_id: "entry-1" }), { status: 200 }));

    await expect(deleteHistory("connection-1", ["entry-1"])).resolves.toEqual(["entry-1"]);
    await expect(getTrash("connection-1")).resolves.toEqual([]);
    await expect(restoreHistory("connection-1", "entry-1")).resolves.toMatchObject({ entry_id: "entry-1" });
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/connections/connection-1/trash/entry-1/restore");
  });

  it("disconnects a connection with a server-side delete request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    await expect(disconnectConnection("connection-1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/connections/connection-1",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    );
  });

  it("reads the free-only entitlement boundary", async () => {
    const entitlement = {
      plan_code: "FREE",
      plan_status: "PREVIEW",
      billing_enabled: false,
      daily_rounds_per_connection: 3,
      total_rounds_per_account: 30,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(entitlement), { status: 200 }),
    );

    await expect(getEntitlements()).resolves.toEqual(entitlement);
    expect(fetch).toHaveBeenCalledWith(
      "/api/entitlements",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("reads usage after the server-side round charge boundary", async () => {
    const usage = {
      usage_date: "2026-09-22",
      connection_used: 2,
      connection_limit: 3,
      account_used: 5,
      account_limit: 30,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(usage), { status: 200 }),
    );

    await expect(getUsage("connection-1")).resolves.toEqual(usage);
    expect(fetch).toHaveBeenCalledWith(
      "/api/connections/connection-1/usage",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
