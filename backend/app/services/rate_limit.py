import logging
import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

logger = logging.getLogger("ecoplant.rate_limit")

# Valores confirmados con Luis (2026-10-26): 5 fallos seguidos bloquean
# ese email 15 minutos; la IP aguanta mas (varias personas/emails detras
# de la misma conexion) pero tambien se bloquea si pasa de 20 en la misma
# ventana. 5 y no 3: con 3, un despiste al teclear dejaria fuera a
# cualquiera de la familia, y cualquiera que conozca tu email podria
# bloquearte a proposito - un bloqueo corto basta para frenar la fuerza
# bruta (de miles de intentos por hora a ~20) sin dejar a nadie fuera.
LOGIN_EMAIL_MAX_FAILURES = 5
LOGIN_IP_MAX_FAILURES = 20
FAILURE_WINDOW_SECONDS = 15 * 60
LOCK_SECONDS = 15 * 60

REGISTER_MAX_ATTEMPTS = 5
REGISTER_WINDOW_SECONDS = 60 * 60

# Tope de claves distintas que se recuerdan a la vez, para que un
# atacante que pruebe millones de emails distintos no pueda llenar la
# memoria del proceso (las entradas viejas se limpian antes de llegar).
_MAX_TRACKED_KEYS = 10_000

LOOPBACK_PEERS = {"127.0.0.1", "::1"}


class _FailureTracker:
    def __init__(self, max_failures: int, window_seconds: int, lock_seconds: int) -> None:
        self._max_failures = max_failures
        self._window = window_seconds
        self._lock_seconds = lock_seconds
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._mutex = threading.Lock()

    def retry_after(self, key: str, now: float) -> int:
        with self._mutex:
            until = self._locked_until.get(key)
            if until is None:
                return 0
            if until <= now:
                del self._locked_until[key]
                return 0
            return math.ceil(until - now)

    def record_failure(self, key: str, now: float) -> bool:
        # True si este fallo dispara el bloqueo.
        with self._mutex:
            self._cleanup(now)
            attempts = self._failures.setdefault(key, deque())
            attempts.append(now)
            while attempts and now - attempts[0] > self._window:
                attempts.popleft()
            if len(attempts) >= self._max_failures:
                self._locked_until[key] = now + self._lock_seconds
                del self._failures[key]
                return True
            return False

    def reset(self, key: str) -> None:
        with self._mutex:
            self._failures.pop(key, None)

    def _cleanup(self, now: float) -> None:
        if len(self._failures) + len(self._locked_until) < _MAX_TRACKED_KEYS:
            return
        for key in [k for k, v in self._failures.items() if not v or now - v[-1] > self._window]:
            del self._failures[key]
        for key in [k for k, until in self._locked_until.items() if until <= now]:
            del self._locked_until[key]


class _AttemptCounter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._mutex = threading.Lock()

    def check_and_count(self, key: str, now: float) -> int:
        # 0 si se permite (y cuenta el intento), o los segundos que faltan
        # hasta que se libere un hueco si ya se llego al maximo.
        with self._mutex:
            if len(self._attempts) >= _MAX_TRACKED_KEYS:
                for k in [k for k, v in self._attempts.items() if not v or now - v[-1] > self._window]:
                    del self._attempts[k]
            attempts = self._attempts.setdefault(key, deque())
            while attempts and now - attempts[0] > self._window:
                attempts.popleft()
            if len(attempts) >= self._max_attempts:
                return math.ceil(self._window - (now - attempts[0]))
            attempts.append(now)
            return 0


_email_failures = _FailureTracker(LOGIN_EMAIL_MAX_FAILURES, FAILURE_WINDOW_SECONDS, LOCK_SECONDS)
_ip_failures = _FailureTracker(LOGIN_IP_MAX_FAILURES, FAILURE_WINDOW_SECONDS, LOCK_SECONDS)
_register_attempts = _AttemptCounter(REGISTER_MAX_ATTEMPTS, REGISTER_WINDOW_SECONDS)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _too_many_requests(retry_after_seconds: int) -> HTTPException:
    minutes = max(1, math.ceil(retry_after_seconds / 60))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos. Vuelve a probar en {minutes} min.",
        headers={"Retry-After": str(retry_after_seconds)},
    )


def client_ip(request: Request) -> str:
    # Detras de Caddy + Cloudflare Tunnel el backend ve siempre
    # 127.0.0.1 como origen: la IP real llega en CF-Connecting-IP, que
    # solo se acepta cuando la conexion viene de loopback (cloudflared y
    # Caddy corren en la propia Pi). Alguien en la LAN que hable
    # directamente con Caddy podria falsear esa cabecera para esquivar
    # el limite por IP - el limite por email sigue valiendo igual.
    peer = request.client.host if request.client else "desconocida"
    if peer in LOOPBACK_PEERS:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded.strip()
    return peer


def check_login_allowed(email: str, ip: str, now: float | None = None) -> None:
    current = time.time() if now is None else now
    wait = max(
        _ip_failures.retry_after(ip, current),
        _email_failures.retry_after(_normalize_email(email), current),
    )
    if wait > 0:
        raise _too_many_requests(wait)


def record_login_failure(email: str, ip: str, now: float | None = None) -> None:
    current = time.time() if now is None else now
    logger.warning("Login fallido desde %s", ip)
    if _email_failures.record_failure(_normalize_email(email), current):
        logger.warning("Email bloqueado %d min por demasiados fallos (ultimo desde %s)", LOCK_SECONDS // 60, ip)
    if _ip_failures.record_failure(ip, current):
        logger.warning("IP %s bloqueada %d min por demasiados fallos", ip, LOCK_SECONDS // 60)


def record_login_success(email: str) -> None:
    # Solo se limpia el contador del email: el de la IP sigue su curso -
    # si no, alguien con una cuenta propia podria intercalar logins
    # correctos para resetear el contador mientras prueba contraseñas
    # ajenas.
    _email_failures.reset(_normalize_email(email))


def check_register_allowed(ip: str, now: float | None = None) -> None:
    current = time.time() if now is None else now
    wait = _register_attempts.check_and_count(ip, current)
    if wait > 0:
        logger.warning("Registro bloqueado por exceso de intentos desde %s", ip)
        raise _too_many_requests(wait)
