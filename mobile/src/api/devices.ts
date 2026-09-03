import { apiRequest } from "./client";
import type { DeviceOut, ReadingsOut } from "../types/api";

export function listDevices(): Promise<DeviceOut[]> {
  return apiRequest<DeviceOut[]>("/api/devices");
}

export function getDevice(deviceId: string): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}`);
}

export function claimDevice(deviceId: string, claimCode: string, locationId: string): Promise<DeviceOut> {
  return apiRequest<DeviceOut>("/api/devices/claim", {
    method: "POST",
    body: JSON.stringify({ device_id: deviceId, claim_code: claimCode, location_id: locationId }),
  });
}

export function unclaimDevice(deviceId: string): Promise<void> {
  return apiRequest<void>(`/api/devices/${deviceId}`, { method: "DELETE" });
}

export function renameDevice(deviceId: string, name: string): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function getReadings(deviceId: string, hours = 24): Promise<ReadingsOut> {
  return apiRequest<ReadingsOut>(`/api/devices/${deviceId}/readings?hours=${hours}`);
}

export function waterDevice(deviceId: string): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/api/devices/${deviceId}/water`, { method: "POST" });
}
