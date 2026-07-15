// The one place that speaks HTTP. Everything else calls typed functions.

export interface ApiErrorBody {
  error: string;
  detail?: Record<string, unknown>;
}

export class ApiError extends Error {
  status: number;
  detail: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error || `Request failed (${status})`);
    this.status = status;
    this.detail = body.detail ?? {};
  }

  /** Field-level validation messages (422), if present. */
  get fields(): Record<string, string> {
    const f = this.detail.fields;
    return f && typeof f === "object" ? (f as Record<string, string>) : {};
  }

  /** 409 blockedBy detail formatted as a readable string. */
  get blockedByMessage(): string | null {
    const b = this.detail.blockedBy;
    if (!b || typeof b !== "object") return null;
    const blocked = b as Record<string, unknown>;
    const parts: string[] = [];
    if (blocked.reason && typeof blocked.reason === "string") return blocked.reason;
    const labels: Record<string, string> = {
      relationships: "soft relationship",
      dependencies: "dependency",
      todos: "todo",
      conversations: "conversation",
      plotlines: "plotline",
      jobs: "running job",
    };
    for (const [key, label] of Object.entries(labels)) {
      const arr = blocked[key];
      if (Array.isArray(arr) && arr.length > 0) {
        parts.push(`${arr.length} ${label}${arr.length > 1 ? (key === "dependency" ? "ies" : "s") : ""}`);
      }
    }
    return parts.length > 0 ? `Blocked by: ${parts.join(", ")}` : null;
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, (body as ApiErrorBody) ?? { error: res.statusText });
  }
  return body as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`/api${path}`));
}

export async function apiSend<T>(method: string, path: string, body?: unknown): Promise<T> {
  return parse<T>(
    await fetch(`/api${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

// Multipart uploads (e.g. book cover). No Content-Type header — the browser
// sets the multipart boundary itself.
export async function apiUpload<T>(method: string, path: string, form: FormData): Promise<T> {
  return parse<T>(await fetch(`/api${path}`, { method, body: form }));
}
