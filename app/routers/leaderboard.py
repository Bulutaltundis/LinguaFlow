from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.models.xp_event import XPEvent
from app.models.classroom import Classroom, ClassMembership


templates = Jinja2Templates(
    directory="app/templates"
)


router = APIRouter(
    tags=["Leaderboard"],
)


@router.get(
    "/leaderboard",
    response_class=HTMLResponse,
)
def leaderboard(
    request: Request,
    class_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    if not user:
        return RedirectResponse(
            "/auth/login",
            status_code=303,
        )

    now = datetime.now(timezone.utc)

    # Haftanın başlangıcı: Pazartesi 00:00
    week_start = (
        now - timedelta(days=now.weekday())
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if class_id is None:
        saved_class = request.cookies.get("active_class_id")
        class_id = int(saved_class) if saved_class and saved_class.isdigit() else None
    active_class = session.get(Classroom, class_id) if class_id else None
    if active_class and active_class.teacher_id != user.id and not session.exec(select(ClassMembership).where((ClassMembership.classroom_id == active_class.id) & (ClassMembership.user_id == user.id))).first():
        active_class = None
    member_ids = None
    if active_class:
        member_ids = [active_class.teacher_id] + [m.user_id for m in session.exec(select(ClassMembership).where(ClassMembership.classroom_id == active_class.id)).all()]
    statement = (
        select(
            XPEvent.user_id,
            func.sum(XPEvent.amount).label(
                "weekly_xp"
            ),
        )
        .where(
            XPEvent.created_at >= week_start
        )
        .group_by(XPEvent.user_id)
        .order_by(
            func.sum(XPEvent.amount).desc()
        )
    )
    if member_ids is not None:
        statement = statement.where(XPEvent.user_id.in_(member_ids))

    results = session.exec(statement).all()

    leaderboard_users = []

    for position, row in enumerate(
        results,
        start=1,
    ):
        leaderboard_user = session.get(
            User,
            row.user_id,
        )

        if not leaderboard_user:
            continue

        leaderboard_users.append(
            {
                "position": position,
                "user": leaderboard_user,
                "xp": row.weekly_xp or 0,
            }
        )

    current_entry = next(
        (
            entry
            for entry in leaderboard_users
            if entry["user"].id == user.id
        ),
        None,
    )

    return templates.TemplateResponse(
        request=request,
        name="leaderboard/index.html",
        context={
            "user": user,
            "leaderboard": leaderboard_users,
            "current_entry": current_entry,
            "week_start": week_start,
            "active_class": active_class,
        },
    )
