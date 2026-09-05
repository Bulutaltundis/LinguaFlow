import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request
from sqlmodel import Session, select
from app.models.session import UserSession
from app.models.user import User
SESSION_COOKIE = "linguaflow_session"
CSRF_COOKIE = "linguaflow_csrf"
SESSION_DAYS = 14
def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
def create_session(user: User, session: Session):
    now = datetime.now(timezone.utc)
    for old in session.exec(select(UserSession).where((UserSession.user_id == user.id) & (UserSession.revoked_at == None))).all():
        old.revoked_at = now
        session.add(old)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    session.add(UserSession(user_id=user.id, token_hash=digest(token), csrf_hash=digest(csrf), expires_at=now + timedelta(days=SESSION_DAYS)))
    session.commit()
    return token, csrf
def get_session_record(request: Request, session: Session):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    record = session.exec(select(UserSession).where(UserSession.token_hash == digest(token))).first()
    expires = record.expires_at.replace(tzinfo=timezone.utc) if record and record.expires_at.tzinfo is None else (record.expires_at if record else None)
    if not record or record.revoked_at or not expires or expires < datetime.now(timezone.utc):
        return None
    return record
def get_current_user(request: Request, session: Session) -> User | None:
    record = get_session_record(request, session)
    return session.get(User, record.user_id) if record else None
def revoke_session(request: Request, session: Session):
    record = get_session_record(request, session)
    if record:
        record.revoked_at = datetime.now(timezone.utc)
        session.add(record)
        session.commit()
def cookie_kwargs(request: Request):
    return {"httponly": True, "secure": request.url.scheme == "https", "samesite": "lax", "max_age": SESSION_DAYS * 86400}
