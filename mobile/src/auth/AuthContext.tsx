import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import * as authApi from "../api/auth";
import { registerSessionExpiredHandler } from "../api/client";
import type { UserOut } from "../types/api";
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from "./secureStorage";

interface AuthContextValue {
  user: UserOut | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    registerSessionExpiredHandler(() => setUser(null));

    // Al abrir la app, si hay un token guardado se comprueba que
    // sigue siendo valido (o se refresca solo, via el interceptor de
    // apiRequest) pidiendo el perfil - si falla del todo, se queda
    // sin sesion y la navegacion manda a Login.
    (async () => {
      const token = await getAccessToken();
      if (token) {
        try {
          setUser(await authApi.me());
        } catch {
          setUser(null);
        }
      }
      setIsLoading(false);
    })();
  }, []);

  async function login(email: string, password: string) {
    const tokens = await authApi.login(email, password);
    await saveTokens(tokens.access_token, tokens.refresh_token);
    setUser(await authApi.me());
  }

  async function register(email: string, password: string, fullName?: string) {
    const tokens = await authApi.register(email, password, fullName);
    await saveTokens(tokens.access_token, tokens.refresh_token);
    setUser(await authApi.me());
  }

  async function logout() {
    const refreshToken = await getRefreshToken();
    if (refreshToken) {
      await authApi.logout(refreshToken).catch(() => undefined);
    }
    await clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
