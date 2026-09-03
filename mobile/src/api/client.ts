import { clearTokens, getAccessToken, getApiBaseUrl, getRefreshToken, saveTokens } from "../auth/secureStorage";
import type { ApiError as ApiErrorBody, TokenPair } from "../types/api";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

// Se registra desde AuthContext para poder forzar el logout cuando el
// refresh token tambien falla, sin crear una dependencia circular
// entre este archivo y el contexto de autenticacion.
let onSessionExpired: (() => void) | null = null;
export function registerSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;

  const baseUrl = await getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) return null;

  const tokens: TokenPair = await response.json();
  await saveTokens(tokens.access_token, tokens.refresh_token);
  return tokens.access_token;
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
  const baseUrl = await getApiBaseUrl();
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (!options.skipAuth) {
    const accessToken = await getAccessToken();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });

  if (response.status === 401 && !options.skipAuth && !isRetry) {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      return apiRequest<T>(path, options, true);
    }
    await clearTokens();
    onSessionExpired?.();
    throw new ApiError(401, "Sesión expirada");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as ApiErrorBody | null)?.detail ?? "Error inesperado";
    throw new ApiError(response.status, detail);
  }

  return body as T;
}
