from fastapi import Request
from sqlmodel import Session

from app.models.user import User


def get_current_user(
    request: Request,
    session: Session,
) -> User | None:

    user_id = request.cookies.get("session_user_id")

    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    return session.get(User, user_id)