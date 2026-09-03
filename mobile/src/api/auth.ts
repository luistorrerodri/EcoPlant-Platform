import { apiRequest } from "./client";
import type { TokenPair, UserOut } from "../types/api";

export function register(email: string, password: string, fullName?: string): Promise<TokenPair> {
  return apiRequest<TokenPair>("/api/auth/register", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ email, password, full_name: fullName ?? null }),
  });
}

export function login(email: string, password: string): Promise<TokenPair> {
  // El backend usa el flujo estandar OAuth2 (form-urlencoded, campo
  // "username" aunque aqui viaje el email), no JSON.
  const body = new URLSearchParams({ username: email, password }).toString();
  return apiRequest<TokenPair>("/api/auth/login", {
    method: "POST",
    skipAuth: true,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
}

export function logout(refreshToken: string): Promise<void> {
  return apiRequest<void>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export function me(): Promise<UserOut> {
  return apiRequest<UserOut>("/api/auth/me");
}

export function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  return apiRequest<void>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}
