import { apiRequest } from "./client";
import { getAccessToken, getApiBaseUrl } from "../auth/secureStorage";
import type { DeviceEnvironment, DeviceOut, HealthSummaryOut, PhotoDiagnosisOut, ReadingsOut } from "../types/api";

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

export interface DeviceConfigUpdate {
  name?: string;
  plant_type_id?: string | null;
  humedad_min?: number;
  humedad_max?: number;
  hora_inicio?: number;
  hora_fin?: number;
  environment?: DeviceEnvironment;
}

export function updateDeviceConfig(deviceId: string, config: DeviceConfigUpdate): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}`, {
    method: "PATCH",
    body: JSON.stringify(config),
  });
}

export function getReadings(deviceId: string, hours = 24): Promise<ReadingsOut> {
  return apiRequest<ReadingsOut>(`/api/devices/${deviceId}/readings?hours=${hours}`);
}

export function waterDevice(deviceId: string): Promise<{ status: string }> {
  return apiRequest<{ status: string }>(`/api/devices/${deviceId}/water`, { method: "POST" });
}

export function getHealthSummary(deviceId: string): Promise<HealthSummaryOut> {
  return apiRequest<HealthSummaryOut>(`/api/devices/${deviceId}/health-summary`);
}

export function refreshHealthSummary(deviceId: string): Promise<HealthSummaryOut> {
  return apiRequest<HealthSummaryOut>(`/api/devices/${deviceId}/health-summary/refresh`, { method: "POST" });
}

export function calibrateDevice(deviceId: string, punto: "seco" | "humedo"): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}/calibrate`, {
    method: "POST",
    body: JSON.stringify({ punto }),
  });
}

export function submitPhotoDiagnosis(deviceId: string, photoUri: string): Promise<PhotoDiagnosisOut> {
  const formData = new FormData();
  // RN acepta este objeto {uri, name, type} como si fuera un Blob al
  // construir el FormData - patron estandar para subir ficheros locales.
  formData.append("photo", {
    uri: photoUri,
    name: "planta.jpg",
    type: "image/jpeg",
  } as unknown as Blob);
  return apiRequest<PhotoDiagnosisOut>(`/api/devices/${deviceId}/photo-diagnosis`, {
    method: "POST",
    body: formData,
  });
}

export function getPhotoDiagnosis(deviceId: string): Promise<PhotoDiagnosisOut> {
  return apiRequest<PhotoDiagnosisOut>(`/api/devices/${deviceId}/photo-diagnosis`);
}

// La miniatura de la foto no pasa por apiRequest (esa solo sabe parsear
// JSON) - <Image> de React Native soporta pasarle sus propias cabeceras
// para una URL autenticada, así que solo hace falta construir la URL y
// el token vigente.
export async function getPhotoDiagnosisImageSource(
  deviceId: string,
  cacheKey?: string
): Promise<{ uri: string; headers: Record<string, string> }> {
  const baseUrl = await getApiBaseUrl();
  const accessToken = await getAccessToken();
  // cacheKey (normalmente el created_at del diagnostico) evita que el
  // cache de imagenes del sistema se quede con la foto vieja bajo la
  // misma URL cuando se sube una nueva.
  const cacheParam = cacheKey ? `?t=${encodeURIComponent(cacheKey)}` : "";
  return {
    uri: `${baseUrl}/api/devices/${deviceId}/photo-diagnosis/image${cacheParam}`,
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  };
}
