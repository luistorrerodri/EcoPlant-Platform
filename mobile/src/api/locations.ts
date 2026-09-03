import { apiRequest } from "./client";
import type { LocationOut } from "../types/api";

export function listLocations(): Promise<LocationOut[]> {
  return apiRequest<LocationOut[]>("/api/locations");
}

export function createLocation(name: string, description?: string): Promise<LocationOut> {
  return apiRequest<LocationOut>("/api/locations", {
    method: "POST",
    body: JSON.stringify({ name, description: description ?? null }),
  });
}

export function getLocation(id: string): Promise<LocationOut> {
  return apiRequest<LocationOut>(`/api/locations/${id}`);
}

export function deleteLocation(id: string): Promise<void> {
  return apiRequest<void>(`/api/locations/${id}`, { method: "DELETE" });
}
