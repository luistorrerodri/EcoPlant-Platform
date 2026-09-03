// Sin URL fija en duro: se guarda en SecureStore y se puede cambiar
// desde ProfileScreen sin recompilar. Por defecto apunta a la Pi por
// la LAN de casa; cuando exista el dominio de is-a.dev + tunel con
// nombre, ese sera el nuevo valor por defecto (un solo sitio a
// cambiar, no hay que tocar el resto de la app).
export const DEFAULT_API_BASE_URL = "http://192.168.1.140:8080";

export const SECURE_STORE_KEYS = {
  apiBaseUrl: "ecoplant_api_base_url",
  accessToken: "ecoplant_access_token",
  refreshToken: "ecoplant_refresh_token",
} as const;
