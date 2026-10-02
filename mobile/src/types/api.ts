// Reflejan 1:1 los schemas Pydantic de backend/app/schemas/*.py

export interface UserOut {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LocationOut {
  id: string;
  name: string;
  description: string | null;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
}

export type DeviceEnvironment = "interior" | "exterior";

export interface DeviceOut {
  device_id: string;
  name: string | null;
  location_id: string | null;
  plant_type_id: string | null;
  humedad_min: number;
  humedad_max: number;
  hora_inicio: number;
  hora_fin: number;
  duracion_riego_ms: number;
  environment: DeviceEnvironment | null;
  soil_dry_raw: number;
  soil_wet_raw: number;
  sensor_pausado_hasta: string | null;
  claimed_at: string | null;
  created_at: string;
}

export type PlantTypeCategory = "planta" | "hoja_grande" | "colgante" | "crasa" | "palmera" | "arbol";

export interface PlantTypeOut {
  id: string;
  slug: string;
  name: string;
  category: PlantTypeCategory;
  default_humedad_min: number;
  default_humedad_max: number;
  default_hora_inicio: number;
  default_hora_fin: number;
  default_duracion_riego_ms: number;
}

export interface ReadingPoint {
  time: string;
  field: "humedad_suelo" | "temp_aire" | "presion" | "temp_suelo" | "humedad_ambiente";
  value: number;
}

export interface ReadingsOut {
  device_id: string;
  latest_estado: string | null;
  points: ReadingPoint[];
}

export interface LatestReadingsOut {
  humedad_suelo: number | null;
  temp_suelo: number | null;
  temp_aire: number | null;
  presion: number | null;
  humedad_ambiente: number | null;
}

export type HealthVerdict = "sana" | "revisar_riego" | "revisar_drenaje" | "datos_insuficientes";

export interface HealthSummaryOut {
  id: string;
  device_id: string;
  window_days: number;
  verdict: HealthVerdict;
  message: string;
  pct_tiempo_bajo_minimo: number | null;
  pct_tiempo_saturado: number | null;
  num_riegos: number | null;
  tiempo_recuperacion_medio_h: number | null;
  temp_suelo_min: number | null;
  temp_suelo_max: number | null;
  temp_aire_min: number | null;
  temp_aire_max: number | null;
  tasa_secado_pct_h: number | null;
  created_at: string;
}

export type PhotoVerdict = "bien" | "revisar" | "preocupante";

export interface PhotoDiagnosisOut {
  device_id: string;
  verdict: PhotoVerdict;
  message: string;
  created_at: string;
}

export interface ApiError {
  detail: string;
}
