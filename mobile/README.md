# App móvil

App React Native (Expo, TypeScript) para EcoPlant Platform: login/registro, ubicaciones, reclamación y control de dispositivos, histórico con gráficos, riego manual y notificaciones push. Consume la misma API que cualquier otro cliente futuro (portal web incluido) — ver [`../backend/README.md`](../backend/README.md) para el contrato de la API, y [`../docs/architecture.md`](../docs/architecture.md#app-móvil) para el porqué de las decisiones de diseño.

## Requisitos

- Node.js 20+
- La app **Expo Go** ya no sirve para probar esto de verdad: las notificaciones push necesitan una build de desarrollo propia (ver más abajo)
- Backend en marcha y alcanzable desde el móvil — por LAN (`http://192.168.1.140:8080`, con Caddy escuchando también en la IP de la red local) o por el túnel de Cloudflare

## Arrancar en desarrollo

```bash
npm install
npx expo start --dev-client
```

Escanea el QR **desde la app EcoPlant instalada en el móvil** (no desde la cámara ni desde Expo Go). El código JavaScript recarga en caliente igual que con Expo Go — solo hace falta una build nueva cuando cambia algo nativo (nuevas librerías con módulos nativos, `app.json`, `google-services.json`).

## Build de desarrollo (EAS)

Necesaria para poder probar notificaciones push en Android (Expo las quitó de Expo Go desde el SDK 53).

```bash
npm install -g eas-cli
eas login
eas build --platform android --profile development
```

Descarga e instala el APK resultante en el móvil (enlace o QR al terminar la build, ~10-15 min). El perfil `development` está definido en `eas.json`.

## Notificaciones push (Firebase/FCM)

Requiere un proyecto de Firebase vinculado (uno ya creado para este proyecto, `ecoplant-51a78`):

1. `google-services.json` en la raíz de `mobile/`, referenciado en `app.json` (`android.googleServicesFile`) — es contenido público, seguro de subir al repositorio.
2. Una clave de cuenta de servicio de Firebase (Firebase Console → Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada) subida a EAS con `eas credentials` → Android → Google Service Account → *Push Notifications (FCM V1)*. **Esta clave nunca se sube al repositorio** — vive cifrada en EAS.

Si se regenera el proyecto de Firebase o se pierde la clave, hay que repetir el paso 2.

## URL del servidor

No está fija en el código: se guarda en `SecureStore` y se edita desde la pestaña **Perfil** de la propia app (por defecto, la IP de la Pi en la LAN — `src/config.ts`). Así se puede cambiar entre la red local y una URL de Cloudflare Tunnel sin recompilar.

## Estructura del proyecto

```
mobile/
├── app.json / eas.json       # configuración de Expo / EAS Build
├── google-services.json      # Firebase (contenido público)
├── App.tsx                   # providers (React Query, Auth) + navegación
├── src/
│   ├── config.ts              # URL de API por defecto, claves de SecureStore
│   ├── notifications.ts       # permiso, token de push, registro en el backend
│   ├── types/api.ts           # tipos TS que reflejan los schemas Pydantic del backend
│   ├── api/                   # un archivo por recurso: auth, locations, devices, notifications
│   │   └── client.ts           # fetch wrapper con reintento automático tras 401 (refresh token)
│   ├── auth/
│   │   ├── secureStorage.ts    # tokens y URL del servidor en Expo SecureStore
│   │   └── AuthContext.tsx     # sesión actual, login()/register()/logout()
│   ├── navigation/             # AuthStack (login/registro) vs AppTabs (ubicaciones/perfil)
│   ├── screens/
│   └── components/
```

## Autenticación

Mismo modelo que el backend (`docs/architecture.md` § Backend multiusuario): `access_token` corto (30 min) + `refresh_token` revocable. `src/api/client.ts` adjunta el token en cada petición y, si recibe `401`, intenta refrescar una vez antes de forzar el logout — probado de verdad bajando temporalmente `ACCESS_TOKEN_EXPIRE_MINUTES` en el backend.

## Verificación

Con el móvil en la misma red que el backend: registro/login, crear una ubicación, reclamar un dispositivo (`POST /api/admin/devices/seed` desde el Swagger del backend da el `device_id`+`claim_code`), ver su histórico, regarlo y comprobar que la bomba se activa de verdad. Apagar el dispositivo confirma que llega la notificación push de desconexión.
