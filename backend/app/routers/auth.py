from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
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

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
def register(data: UserCreate, db: Session = Depends(get_db)) -> TokenPair:
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
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenPair:
    # El formulario OAuth2 estandar usa "username": aqui viaja el email.
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")
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
