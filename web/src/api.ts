// Small client for the JobsAlert API: attaches the session token to state-changing
// requests and turns failures into readable errors.

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const TOKEN_KEY = 'jobsalert.apiToken';
let tokenRequest: Promise<string> | null = null;

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeStoredToken(token: string | null): void {
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Storage can be unavailable (private mode); the token is simply asked for again.
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === 'string') return detail;
    }
  } catch {
    // Not a JSON error body.
  }
  return `Request failed (HTTP ${res.status})`;
}

async function fetchToken(): Promise<string> {
  const res = await fetch('/api/session');
  if (res.ok) {
    const body = (await res.json()) as { token: string };
    return body.token;
  }
  if (res.status === 403) {
    // Remote access: the server only hands the token to this machine, so ask for it.
    const saved = readStoredToken();
    if (saved) return saved;
    const entered = (window.prompt('Enter the JobsAlert API token (JOBSALERT_API_TOKEN):') ?? '').trim();
    if (!entered) throw new ApiError(401, 'An API token is required to change settings.');
    writeStoredToken(entered);
    return entered;
  }
  throw new ApiError(res.status, await readError(res));
}

function getToken(refresh: boolean): Promise<string> {
  if (refresh || !tokenRequest) {
    const request = fetchToken();
    request.catch(() => {
      tokenRequest = null;
    });
    tokenRequest = request;
  }
  return tokenRequest;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const needsToken = method !== 'GET';

  const send = async (refreshToken: boolean): Promise<Response> => {
    const headers = new Headers(init.headers);
    if (init.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (needsToken) {
      headers.set('X-JobsAlert-Token', await getToken(refreshToken));
    }
    return fetch(path, { ...init, method, headers });
  };

  let res: Response;
  try {
    res = await send(false);
    if (needsToken && res.status === 401) {
      writeStoredToken(null);
      res = await send(true);
    }
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'Cannot reach the JobsAlert API. Start it with `python run.py --server`.');
  }

  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  return (await res.json()) as T;
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
}

export function deleteJson<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
