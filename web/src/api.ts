export interface HealthResponse {
  status: string;
  database: string;
  timestamp: string;
}

export interface PhotoSummary {
  id: string;
  filename: string | null;
  content_type: string;
  size: number;
  width: number;
  height: number;
  created_at: string | null;
  url: string;
}

export interface UserSummary {
  id: string;
  login_identifier: string;
  status: string;
  created_at: string;
}

export interface EntitlementSummary {
  plan_code: string;
  plan_status: string;
  billing_enabled: boolean;
  daily_rounds_per_connection: number;
  total_rounds_per_account: number;
}

export interface InviteSummary {
  code: string;
  expires_at: string;
}

export interface ConnectionSummary {
  id: string;
  partner_user_id: string;
  status: string;
  created_at: string;
}

export interface InboxItem {
  round_id: string;
  connection_id: string;
  status: string;
  created_at: string;
  expires_at: string;
  input: {
    id: string;
    content_type: string;
    size: number;
    width: number;
    height: number;
    created_at: string;
    url: string;
  };
}

export interface DraftResponse {
  id: string;
  round_id: string;
  version: number;
  document: {
    strokes: unknown[];
    layers: unknown[];
    rotation?: number;
    brightness?: number;
    cropSquare?: boolean;
  };
  preview: InboxItem["input"] | null;
  updated_at: string;
  expires_at: string;
}

export interface SubmissionResponse {
  id: string;
  round_id: string;
  status: string;
  result: InboxItem["input"];
  submitted_at: string;
}

export interface ResultSummary {
  submission_id: string;
  is_mine: boolean;
  visibility: "MOSAIC" | "ORIGINAL";
  content_type: string;
  size: number;
  width: number;
  height: number;
  submitted_at: string;
  url: string;
}

export interface HistoryItem {
  entry_id: string;
  connection_id: string;
  round_id: string;
  submission_id: string;
  is_mine: boolean;
  content_type: string;
  size: number;
  width: number;
  height: number;
  submitted_at: string;
  revealed_at: string;
  url: string;
}

export interface HistoryTrashItem extends HistoryItem {
  deleted_at: string;
  purge_at: string;
}

export interface AuthCredentials {
  login_identifier: string;
  password: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(
  /\/$/,
  "",
);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body && !(typeof FormData !== "undefined" && init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `API 요청 실패 (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the status-based message when the server has no JSON error body.
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getPhotos(): Promise<PhotoSummary[]> {
  return request<PhotoSummary[]>("/photos");
}

export function getMe(): Promise<UserSummary> {
  return request<UserSummary>("/auth/me");
}

export function getEntitlements(): Promise<EntitlementSummary> {
  return request<EntitlementSummary>("/entitlements");
}

export function register(credentials: AuthCredentials): Promise<UserSummary> {
  return request<UserSummary>("/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function login(credentials: AuthCredentials): Promise<UserSummary> {
  return request<UserSummary>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function getConnections(): Promise<ConnectionSummary[]> {
  return request<ConnectionSummary[]>("/connections");
}

export function getCurrentInvite(): Promise<InviteSummary> {
  return request<InviteSummary>("/invites/current");
}

export function acceptInvite(invite_code: string): Promise<ConnectionSummary> {
  return request<ConnectionSummary>("/connections", {
    method: "POST",
    body: JSON.stringify({ invite_code }),
  });
}

export function issueInvite(): Promise<InviteSummary> {
  return request<InviteSummary>("/invites", { method: "POST" });
}

export function getInbox(connectionId: string): Promise<InboxItem[]> {
  return request<InboxItem[]>(`/connections/${connectionId}/inbox`);
}

export function getAssetUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}

export function uploadLayer(roundId: string, file: File): Promise<InboxItem["input"]> {
  const form = new FormData();
  form.append("file", file);
  return request<InboxItem["input"]>(`/rounds/${roundId}/layers`, {
    method: "POST",
    body: form,
  });
}

export async function getDraft(roundId: string): Promise<DraftResponse | null> {
  try {
    return await request<DraftResponse>(`/rounds/${roundId}/draft`);
  } catch (reason) {
    if (reason instanceof ApiError && reason.status === 404) return null;
    throw reason;
  }
}

export function saveDraft(
  roundId: string,
  document: string,
  preview: Blob | null,
  version = 1,
): Promise<DraftResponse> {
  const form = new FormData();
  form.append("document_json", document);
  form.append("version", String(version));
  if (preview) form.append("file", preview, "draft.png");
  return request<DraftResponse>(`/rounds/${roundId}/draft`, {
    method: "PUT",
    body: form,
  });
}

export function cancelDraft(roundId: string): Promise<void> {
  return request<void>(`/rounds/${roundId}/draft`, { method: "DELETE" });
}

export function submitRound(roundId: string): Promise<SubmissionResponse> {
  return request<SubmissionResponse>(`/rounds/${roundId}/submit`, { method: "POST" });
}

export function getResults(roundId: string): Promise<ResultSummary[]> {
  return request<ResultSummary[]>(`/rounds/${roundId}/results`);
}

export function getHistory(connectionId: string): Promise<HistoryItem[]> {
  return request<HistoryItem[]>(`/connections/${connectionId}/history`);
}

export function deleteHistory(connectionId: string, entryIds: string[]): Promise<string[]> {
  return request<string[]>(`/connections/${connectionId}/history/delete`, {
    method: "POST",
    body: JSON.stringify({ entry_ids: entryIds }),
  });
}

export function getTrash(connectionId: string): Promise<HistoryTrashItem[]> {
  return request<HistoryTrashItem[]>(`/connections/${connectionId}/trash`);
}

export function restoreHistory(connectionId: string, entryId: string): Promise<HistoryItem> {
  return request<HistoryItem>(`/connections/${connectionId}/trash/${entryId}/restore`, { method: "POST" });
}

export function disconnectConnection(connectionId: string): Promise<void> {
  return request<void>(`/connections/${connectionId}`, { method: "DELETE" });
}
