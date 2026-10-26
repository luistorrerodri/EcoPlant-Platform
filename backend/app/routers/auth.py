from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.push_token import PushToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    PushTokenRequest,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserOut,
)
from app.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.services import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash de una contraseña que nadie va a usar: se verifica contra el
# cuando el email no existe, para que "email inexistente" tarde lo mismo
# (un bcrypt completo) que "email existente con contraseña mala" - si no,
# la diferencia de tiempo delata que emails estan registrados. Se calcula
# la primera vez que hace falta, no al importar el modulo.
_dummy_hash: str | None = None


def _verify_against_dummy(password: str) -> None:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("contraseña-de-relleno-sin-uso")
    verify_password(password, _dummy_hash)


def _issue_token_pair(user: User, db: Session) -> TokenPair:
    access_token = create_access_token(user.id)
    raw_refresh_token = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=refresh_token_expiry(),
        )
    )
    db.commit()
    return TokenPair(access_token=access_token, refresh_token=raw_refresh_token)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(request: Request, data: UserCreate, db: Session = Depends(get_db)) -> TokenPair:
    rate_limit.check_register_allowed(rate_limit.client_ip(request))
    if db.query(User).filter(User.email == data.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese email ya está registrado")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_token_pair(user, db)


@router.post("/login", response_model=TokenPair)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenPair:
    # El formulario OAuth2 estandar usa "username": aqui viaja el email.
    email = form_data.username
    ip = rate_limit.client_ip(request)
    # Antes de tocar la BD ni verificar nada: un email/IP bloqueado se
    # rechaza incluso con la contraseña correcta (si no, la fuerza bruta
    # seguiria funcionando durante el bloqueo).
    rate_limit.check_login_allowed(email, ip)

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        _verify_against_dummy(form_data.password)
        password_ok = False
    else:
        password_ok = verify_password(form_data.password, user.hashed_password)
    if not password_ok:
        rate_limit.record_login_failure(email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")
    rate_limit.record_login_success(email)
    return _issue_token_pair(user, db)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    token_hash = hash_refresh_token(data.refresh_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")
    if stored is None or stored.revoked_at is not None:
        raise invalid
    if stored.expires_at < datetime.now(timezone.utc):
        raise invalid

    # Rotacion: el refresh token usado se revoca y se emite uno nuevo,
    # para que un token robado y reutilizado deje rastro (dos usos del
    # mismo token = señal de que algo esta mal).
    stored.revoked_at = datetime.now(timezone.utc)
    db.commit()

    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise invalid
    return _issue_token_pair(user, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, db: Session = Depends(get_db)) -> None:
    token_hash = hash_refresh_token(data.refresh_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/push-token", status_code=status.HTTP_204_NO_CONTENT)
def set_push_token(
    data: PushTokenRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    # Una fila por movil, varias por cuenta. Si el token ya existe (el
    # mismo movil ya habia iniciado sesion antes, quizas con otra
    # cuenta) se reasigna a esta cuenta en vez de duplicarlo.
    existing = db.query(PushToken).filter(PushToken.token == data.push_token).first()
    if existing is None:
        db.add(PushToken(user_id=user.id, token=data.push_token))
    elif existing.user_id != user.id:
        existing.user_id = user.id
    db.commit()


@router.post("/push-token/unregister", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(
    data: PushTokenRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    # Al cerrar sesion: ese movil deja de recibir los avisos de esta
    # cuenta. Solo borra el token si es de este usuario - nadie puede
    # desregistrar el movil de otra cuenta conociendo su token.
    db.query(PushToken).filter(PushToken.token == data.push_token, PushToken.user_id == user.id).delete()
    db.commit()


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña actual incorrecta")

    user.hashed_password = hash_password(data.new_password)
    # Cambiar la contraseña revoca todas las sesiones activas.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()
