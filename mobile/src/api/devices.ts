import { apiRequest, refreshAccessToken } from "./client";
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
  duracion_riego_ms?: number;
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

export function pauseSensor(deviceId: string): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}/pause-sensor`, { method: "POST" });
}

export function resumeSensor(deviceId: string): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}/resume-sensor`, { method: "POST" });
}

export function calibrateDevice(deviceId: string, punto: "seco" | "humedo"): Promise<DeviceOut> {
  return apiRequest<DeviceOut>(`/api/devices/${deviceId}/calibrate`, {
    method: "POST",
    body: JSON.stringify({ punto }),
  });
}

export async function submitPhotoDiagnosis(deviceId: string, photoUri: string): Promise<PhotoDiagnosisOut> {
  // Expo SDK 57 instala expo/fetch como fetch global, y su codificador de
  // FormData ya no acepta el objeto "legacy" de RN {uri, name, type} - solo
  // string, un Blob real, o un objeto con bytes(). Se lee el fichero local
  // como Blob real con el propio fetch (sin depender de ningun modulo
  // nativo nuevo) y se le fija el tipo explicitamente, porque un fetch a
  // un file:// local no siempre trae el content-type correcto.
  const localFile = await fetch(photoUri);
  const rawBlob = await localFile.blob();
  const blob = new Blob([rawBlob], { type: "image/jpeg" });

  const formData = new FormData();
  formData.append("photo", blob, "planta.jpg");
  return apiRequest<PhotoDiagnosisOut>(`/api/devices/${deviceId}/photo-diagnosis`, {
    method: "POST",
    body: formData,
  });
}

export function getPhotoDiagnosis(deviceId: string): Promise<PhotoDiagnosisOut> {
  return apiRequest<PhotoDiagnosisOut>(`/api/devices/${deviceId}/photo-diagnosis`);
}

function blobToDataUri(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("No se pudo leer la imagen"));
    reader.onload = () => resolve(reader.result as string);
    reader.readAsDataURL(blob);
  });
}

// La miniatura de la foto no pasa por apiRequest (esa solo sabe parsear
// JSON). Antes se le pasaban {uri, headers} a <Image> directamente, pero
// las cabeceras personalizadas en <Image> son poco fiables en Android (y
// no se refrescan solas si el access token ya ha caducado) - se vio como
// 401 repetidos en el log del backend. En su lugar, se descarga ya
// autenticada (con el mismo reintento-tras-401 que el resto de la API) y
// se pasa como data URI embebida: no hace falta cabecera ninguna en
// <Image>. Devuelve null si no se puede cargar, para no mostrar un hueco
// vacío donde iría la foto.
export async function getPhotoDiagnosisImageSource(
  deviceId: string,
  cacheKey?: string
): Promise<{ uri: string } | null> {
  const baseUrl = await getApiBaseUrl();
  const path = `/api/devices/${deviceId}/photo-diagnosis/image`;
  // cacheKey (normalmente el created_at del diagnostico) solo es parte de
  // la cache-key local de react-query - no hace falta mandarlo al backend.
  void cacheKey;

  async function fetchOnce(): Promise<Response> {
    const accessToken = await getAccessToken();
    return fetch(`${baseUrl}${path}`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
  }

  try {
    let response = await fetchOnce();
    if (response.status === 401) {
      const newToken = await refreshAccessToken();
      if (!newToken) return null;
      response = await fetchOnce();
    }
    if (!response.ok) return null;
    const blob = await response.blob();
    return { uri: await blobToDataUri(blob) };
  } catch {
    return null;
  }
}
