import { apiRequest } from "./client";

export function registerPushToken(pushToken: string): Promise<void> {
  return apiRequest<void>("/api/auth/push-token", {
    method: "POST",
    body: JSON.stringify({ push_token: pushToken }),
  });
}
