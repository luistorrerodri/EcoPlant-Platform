import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt para contraseñas y codigos de reclamacion: son secretos de
# baja entropia (los elige una persona), hace falta un hash lento que
# resista fuerza bruta. Se verifican con pwd_context.verify(), nunca
# se buscan en la BD por su hash.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_claim_code(code: str) -> str:
    return pwd_context.hash(code)


def verify_claim_code(plain_code: str, hashed_code: str) -> bool:
    return pwd_context.verify(plain_code, hashed_code)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> str:
    # Alta entropia por si sola (256 bits) - a diferencia de una
    # contraseña, no necesita un hash lento, basta uno rapido y
    # determinista para poder buscarlo en la BD por igualdad exacta.
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
