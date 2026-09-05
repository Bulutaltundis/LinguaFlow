from datetime import datetime, timezone

from sqlmodel import Session

from app.models.user import User


def register_activity(user: User, session: Session) -> None:
    """Günlük seriyi günceller; atlanan tek günü seri dondurucu kapatabilir."""
    now = datetime.now(timezone.utc)
    previous = user.last_active
    if previous and previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    if previous is None:
        user.streak = max(1, user.streak)
    elif previous.date() < now.date():
        gap = (now.date() - previous.date()).days
        if gap == 1:
            user.streak += 1
        elif user.streak_freezes > 0:
            user.streak_freezes -= 1
        else:
            user.streak = 1
    user.last_active = now
    session.add(user)
