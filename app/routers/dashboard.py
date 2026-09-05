from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.course import Course
from app.models.lesson import Unit, Lesson
from app.models.progress import UserProgress
from app.models.user import User
from app.models.classroom import Classroom, ClassMembership
from app.core.activity import register_activity
from app.core.auth import get_current_user as auth_current_user

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


def get_current_user(request: Request, session: Session):
    return auth_current_user(request, session)


def calculate_level(xp: int):
    """
    Basit XP → level sistemi.
    Her level için gereken XP giderek artar.
    """
    level = 1
    remaining_xp = xp

    while remaining_xp >= level * 100:
        remaining_xp -= level * 100
        level += 1

    current_requirement = level * 100

    return {
        "level": level,
        "current_xp": remaining_xp,
        "required_xp": current_requirement,
        "progress": int((remaining_xp / current_requirement) * 100),
    }


@router.get("", response_class=HTMLResponse)
def dashboard(
    request: Request,
    class_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    if not user:
        return RedirectResponse(
            url="/auth/login",
            status_code=303,
        )

    register_activity(user, session)

    if class_id is None:
        saved_class = request.cookies.get("active_class_id")
        class_id = int(saved_class) if saved_class and saved_class.isdigit() else None
    active_class = session.get(Classroom, class_id) if class_id else None
    if active_class and active_class.teacher_id != user.id and not session.exec(select(ClassMembership).where((ClassMembership.classroom_id == active_class.id) & (ClassMembership.user_id == user.id))).first():
        active_class = None
    if active_class and active_class.course_id:
        course = session.get(Course, active_class.course_id)
    elif course_id:
        course = session.get(Course, course_id)
    else:
        saved_course = request.cookies.get("selected_course_id")
        course = session.get(Course, int(saved_course)) if saved_course and saved_course.isdigit() else session.exec(select(Course).order_by(Course.id)).first()

    units = []

    if course:
        db_units = session.exec(
            select(Unit)
            .where(Unit.course_id == course.id)
            .order_by(Unit.order)
        ).all()

        for unit in db_units:
            lessons = session.exec(
                select(Lesson)
                .where(Lesson.unit_id == unit.id)
                .order_by(Lesson.order)
            ).all()

            lesson_items = []

            for lesson in lessons:
                progress = session.exec(
                    select(UserProgress)
                    .where(
                        (UserProgress.user_id == user.id)
                        & (UserProgress.lesson_id == lesson.id)
                    )
                ).first()

                completed = bool(progress and progress.completed)

                lesson_items.append(
                    {
                        "lesson": lesson,
                        "completed": completed,
                        "progress": progress,
                    }
                )

            units.append(
                {
                    "unit": unit,
                    "lessons": lesson_items,
                }
            )

    # İlk tamamlanmamış dersi bul.
    current_lesson_id = None

    for unit_data in units:
        for item in unit_data["lessons"]:
            if not item["completed"]:
                current_lesson_id = item["lesson"].id
                break

        if current_lesson_id is not None:
            break

    # Dersleri kilitle:
    # İlk ders açık, sonraki ders ancak önceki tamamlanınca açılır.
    previous_completed = True

    for unit_data in units:
        for item in unit_data["lessons"]:
            item["locked"] = not previous_completed

            if item["completed"]:
                previous_completed = True
            else:
                previous_completed = False

    level_data = calculate_level(user.xp)

    user.level = level_data["level"]

    session.add(user)
    session.commit()

    total_completed = sum(
        1
        for unit_data in units
        for item in unit_data["lessons"]
        if item["completed"]
    )

    total_lessons = sum(
        len(unit_data["lessons"])
        for unit_data in units
    )

    daily_goal = min(user.xp % 50, 50)

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "user": user,
            "course": course,
            "units": units,
            "level": level_data,
            "current_lesson_id": current_lesson_id,
            "completed_lessons": total_completed,
            "total_lessons": total_lessons,
            "daily_goal": daily_goal,
            "active_class": active_class,
        },
    )
