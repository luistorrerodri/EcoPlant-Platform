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
  created_at: string;
}

export interface DeviceOut {
  device_id: string;
  name: string | null;
  location_id: string | null;
  claimed_at: string | null;
  created_at: string;
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
