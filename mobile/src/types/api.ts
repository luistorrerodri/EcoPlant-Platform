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
  hora_inicio: number;
  hora_fin: number;
  duracion_riego_ms: number;
  environment: DeviceEnvironment | null;
  claimed_at: string | null;
  created_at: string;
}

export interface PlantTypeOut {
  id: string;
  slug: string;
  name: string;
  default_humedad_min: number;
  default_hora_inicio: number;
  default_hora_fin: number;
  default_duracion_riego_ms: number;
}

export interface ReadingPoint {
  time: string;
  field: "humedad_suelo" | "temp_aire" | "presion";
  value: number;
}

export interface ReadingsOut {
  device_id: string;
  latest_estado: string | null;
  points: ReadingPoint[];
}

export interface ApiError {
  detail: string;
}
