"""Authentication endpoints: register, login, me, password reset, API keys."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..core.rate_limit import limiter
from ..core.security import hash_password, verify_password, create_access_token
from ..core.deps import get_current_user
from ..models.db_models import User, PasswordResetToken, ApiKey
from ..models.auth_schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    UserPublicResponse,
    UpdateProfileRequest,
    ChangePasswordRequest,
)
from ..services import audit
from ..services import email as email_service

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Auth ─────────────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()
    await audit.log_action(db, user, audit.ACTION_REGISTER, "user", user.id, ip_address=request.client.host)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token(user.id)
    await audit.log_action(db, user, audit.ACTION_LOGIN, ip_address=request.client.host)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    if body.full_name is not None:
        user.full_name = body.full_name
    return user


@router.put("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    return {"status": "password_changed"}


@router.get("/users/search", response_model=list[UserPublicResponse])
async def search_users(
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search users by email prefix (for sharing UI)."""
    if len(q) < 2:
        return []
    result = await db.execute(
        select(User)
        .where(User.email.ilike(f"{q}%"), User.id != user.id, User.is_active.is_(True))
        .limit(10)
    )
    return result.scalars().all()


# ── Password Reset ───────────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset. Always returns 200 to prevent email enumeration."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_password(raw_token)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)

        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires,
        )
        db.add(reset)
        await db.flush()

        email_sent = await email_service.send_password_reset(user.email, raw_token)

        if not email_sent and not email_service.is_email_configured():
            # Dev mode: return token directly when no SMTP configured
            return {
                "status": "token_generated",
                "token": raw_token,
                "note": "SMTP not configured — token returned directly",
            }

    return {"status": "ok", "message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid token."""
    result = await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.used.is_(False),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .options(selectinload(PasswordResetToken.user))
    )
    tokens = result.scalars().all()

    matched = None
    for t in tokens:
        if verify_password(body.token, t.token_hash):
            matched = t
            break

    if not matched:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    matched.used = True
    matched.user.hashed_password = hash_password(body.new_password)
    return {"status": "password_reset"}


# ── API Keys ─────────────────────────────────────────────────────────────────


class ApiKeyCreate(BaseModel):
    name: str


@router.post("/api-keys")
async def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. The full key is returned ONLY in this response."""
    raw_key = f"pk_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:8]
    key_hash = hash_password(raw_key)

    api_key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        prefix=prefix,
    )
    db.add(api_key)
    await db.flush()

    return {
        "id": api_key.id,
        "name": api_key.name,
        "prefix": prefix,
        "key": raw_key,
        "created_at": api_key.created_at.isoformat(),
    }


@router.get("/api-keys")
async def list_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return [
        {
            "id": k.id,
            "name": k.name,
            "prefix": k.prefix,
            "is_active": k.is_active,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat(),
        }
        for k in result.scalars().all()
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(key)
    return {"status": "revoked"}
