// Sin URL fija en duro: se guarda en SecureStore y se puede cambiar
// desde ProfileScreen sin recompilar. Por defecto apunta al dominio
// fijo (tunel con nombre de Cloudflare + ecoplantplatform.com) para
// que la app funcione igual en casa o fuera sin tocar nada; la IP de
// la LAN sigue disponible como alternativa manual en Perfil.
export const DEFAULT_API_BASE_URL = "https://api.ecoplantplatform.com";

export const SECURE_STORE_KEYS = {
  apiBaseUrl: "ecoplant_api_base_url",
  accessToken: "ecoplant_access_token",
  refreshToken: "ecoplant_refresh_token",
} as const;
