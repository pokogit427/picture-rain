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

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(
  /\/$/,
  "",
);

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`);
  if (!response.ok) {
    throw new Error(`API 요청 실패 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("/health");
}

export function getPhotos(): Promise<PhotoSummary[]> {
  return get<PhotoSummary[]>("/photos");
}
