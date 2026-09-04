import { apiRequest } from "./client";
import type { LocationOut } from "../types/api";

export function listLocations(): Promise<LocationOut[]> {
  return apiRequest<LocationOut[]>("/api/locations");
}

export function createLocation(
  name: string,
  description?: string,
  latitude?: number,
  longitude?: number
): Promise<LocationOut> {
  return apiRequest<LocationOut>("/api/locations", {
    method: "POST",
    body: JSON.stringify({
      name,
      description: description ?? null,
      latitude: latitude ?? null,
      longitude: longitude ?? null,
    }),
  });
}

export function getLocation(id: string): Promise<LocationOut> {
  return apiRequest<LocationOut>(`/api/locations/${id}`);
}

export interface LocationUpdate {
  name?: string;
  description?: string;
  latitude?: number;
  longitude?: number;
}

export function updateLocation(id: string, data: LocationUpdate): Promise<LocationOut> {
  return apiRequest<LocationOut>(`/api/locations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteLocation(id: string): Promise<void> {
  return apiRequest<void>(`/api/locations/${id}`, { method: "DELETE" });
}
