import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.classroom import Assignment, ClassMembership, Classroom
from app.models.course import Course
from app.models.lesson import Lesson, Unit
from app.models.shop import ShopItem
from app.models.user import User

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/classes", tags=["Classes"])


def code_for(session: Session) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        raw = "".join(secrets.choice(alphabet) for _ in range(6))
        code = f"{raw[:3]}-{raw[3:]}"
        if not session.exec(select(Classroom).where(Classroom.code == code)).first():
            return code


def membership(session: Session, classroom_id: int, user_id: int):
    return session.exec(select(ClassMembership).where(
        (ClassMembership.classroom_id == classroom_id) & (ClassMembership.user_id == user_id)
    )).first()


def can_manage(room: Classroom, user: User):
    return user.role == "teacher" and room.teacher_id == user.id


@router.get("", response_class=HTMLResponse)
def classes_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    rooms = session.exec(select(Classroom).where(
        (Classroom.teacher_id == user.id) | Classroom.id.in_(
            select(ClassMembership.classroom_id).where(ClassMembership.user_id == user.id)
        )
    ).order_by(Classroom.id.desc())).all()
    courses = session.exec(select(Course).order_by(Course.id)).all()
    room_data = []
    for room in rooms:
        count = len(session.exec(select(ClassMembership).where(ClassMembership.classroom_id == room.id)).all())
        course = session.get(Course, room.course_id) if room.course_id else None
        room_data.append({"room": room, "student_count": count, "course": course})
    return templates.TemplateResponse(request=request, name="classes/index.html", context={"user": user, "rooms": room_data, "courses": courses})


@router.post("/create")
def create_class(request: Request, name: str = Form(...), course_id: int = Form(...), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user or user.role != "teacher":
        return RedirectResponse("/classes?error=teacher_only", status_code=303)
    course = session.get(Course, course_id)
    if not course or not name.strip():
        return RedirectResponse("/classes?error=invalid", status_code=303)
    room = Classroom(name=name.strip(), code=code_for(session), teacher_id=user.id, course_id=course_id)
    session.add(room)
    session.commit()
    session.refresh(room)
    return RedirectResponse(f"/classes/{room.id}", status_code=303)


@router.post("/join")
def join_class(request: Request, code: str = Form(...), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    normalized = code.strip().upper()
    room = session.exec(select(Classroom).where(Classroom.code == normalized)).first()
    if not room:
        return RedirectResponse("/classes?error=invalid_code", status_code=303)
    if not membership(session, room.id, user.id) and room.teacher_id != user.id:
        session.add(ClassMembership(classroom_id=room.id, user_id=user.id))
        session.commit()
    return RedirectResponse(f"/classes/{room.id}", status_code=303)


@router.get("/{classroom_id}", response_class=HTMLResponse)
def class_detail(classroom_id: int, request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    room = session.get(Classroom, classroom_id)
    if not user or not room:
        return RedirectResponse("/classes", status_code=303)
    if room.teacher_id != user.id and not membership(session, room.id, user.id):
        return HTMLResponse("Bu sınıfa erişimin yok.", status_code=403)
    teacher = session.get(User, room.teacher_id)
    members = session.exec(select(ClassMembership).where(ClassMembership.classroom_id == room.id)).all()
    students = [session.get(User, m.user_id) for m in members]
    assignments = session.exec(select(Assignment).where(Assignment.classroom_id == room.id).order_by(Assignment.created_at.desc())).all()
    course = session.get(Course, room.course_id) if room.course_id else None
    items = session.exec(select(ShopItem).where(ShopItem.class_id == room.id).order_by(ShopItem.id.desc())).all()
    lessons = []
    if course:
        lessons = session.exec(select(Lesson).join(Unit).where(Unit.course_id == course.id).order_by(Lesson.order)).all()
    response = templates.TemplateResponse(request=request, name="classes/detail.html", context={"user": user, "room": room, "teacher": teacher, "students": students, "assignments": assignments, "course": course, "lessons": lessons, "items": items, "can_manage": can_manage(room, user), "student_count": len(students), "lesson_count": len(lessons)})
    response.set_cookie("active_class_id", str(room.id), httponly=True, samesite="lax")
    return response


@router.post("/{classroom_id}/assign")
def create_assignment(classroom_id: int, request: Request, title: str = Form(...), lesson_count: int = Form(2), due_at: str = Form(""), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    room = session.get(Classroom, classroom_id)
    if not user or not room or not can_manage(room, user):
        return RedirectResponse(f"/classes/{classroom_id}", status_code=303)
    parsed_due = None
    if due_at:
        try:
            parsed_due = datetime.fromisoformat(due_at)
        except ValueError:
            pass
    session.add(Assignment(classroom_id=classroom_id, title=title.strip() or "Yeni ödev", lesson_count=max(1, lesson_count), due_at=parsed_due))
    session.commit()
    return RedirectResponse(f"/classes/{classroom_id}", status_code=303)


@router.post("/{classroom_id}/shop/create")
def create_class_shop_item(classroom_id: int, request: Request, name: str = Form(...), description: str = Form(""), icon: str = Form("🎁"), price: int = Form(...), type: str = Form(...), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    room = session.get(Classroom, classroom_id)
    allowed = {"heart", "heart_pack", "streak_freeze", "xp_boost", "avatar", "theme", "cosmetic"}
    if not user or not room or not can_manage(room, user) or type not in allowed or price < 0:
        return RedirectResponse(f"/classes/{classroom_id}", status_code=303)
    session.add(ShopItem(name=name.strip(), description=description.strip(), icon=icon.strip() or "🎁", price=price, type=type, class_id=classroom_id))
    session.commit()
    return RedirectResponse(f"/classes/{classroom_id}", status_code=303)
