import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.api_key import APIKey
from app.models.user import User


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_api_key(user: User, session: Session) -> str:
    raw = "lf_" + secrets.token_urlsafe(32)
    session.add(APIKey(
        user_id=user.id,
        key_prefix=raw[:11],
        key_hash=hash_api_key(raw),
        name="mobile",
    ))
    session.commit()
    return raw


def get_api_user(
    x_api_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not x_api_key or len(x_api_key) > 160:
        raise HTTPException(status_code=401, detail="X-API-Key gerekli")
    api_key = session.exec(
        select(APIKey).where(
            (APIKey.key_hash == hash_api_key(x_api_key))
            & (APIKey.revoked_at == None)
        )
    ).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Geçersiz API key")
    user = session.get(User, api_key.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    api_key.last_used_at = datetime.now(timezone.utc)
    session.add(api_key)
    session.commit()
    return user
