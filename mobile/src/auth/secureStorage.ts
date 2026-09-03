import * as SecureStore from "expo-secure-store";

import { DEFAULT_API_BASE_URL, SECURE_STORE_KEYS } from "../config";

// Envoltorio sobre Expo SecureStore (cifrado con el keychain/keystore
// del sistema) - nunca AsyncStorage para tokens, igual que el backend
// nunca guarda contraseñas ni refresh tokens en claro.

export async function saveTokens(accessToken: string, refreshToken: string): Promise<void> {
  await SecureStore.setItemAsync(SECURE_STORE_KEYS.accessToken, accessToken);
  await SecureStore.setItemAsync(SECURE_STORE_KEYS.refreshToken, refreshToken);
}

export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(SECURE_STORE_KEYS.accessToken);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(SECURE_STORE_KEYS.refreshToken);
}

export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(SECURE_STORE_KEYS.accessToken);
  await SecureStore.deleteItemAsync(SECURE_STORE_KEYS.refreshToken);
}

export async function getApiBaseUrl(): Promise<string> {
  const stored = await SecureStore.getItemAsync(SECURE_STORE_KEYS.apiBaseUrl);
  return stored ?? DEFAULT_API_BASE_URL;
}

export async function setApiBaseUrl(url: string): Promise<void> {
  await SecureStore.setItemAsync(SECURE_STORE_KEYS.apiBaseUrl, url);
}
