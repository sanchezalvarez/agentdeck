export const API_URL =
  process.env.NEXT_PUBLIC_AGENT_HUB_URL ?? "http://127.0.0.1:8765";

// Local-only deployment: the token (if any) is exposed to the browser on this
// machine. Keep the backend bound to localhost.
const WRITE_TOKEN = process.env.NEXT_PUBLIC_AGENT_HUB_WRITE_TOKEN ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  return handle<T>(response);
}

function writeHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (WRITE_TOKEN) headers["Authorization"] = `Bearer ${WRITE_TOKEN}`;
  return headers;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: writeHeaders(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(response);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
    headers: writeHeaders(),
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}
