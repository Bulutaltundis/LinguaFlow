from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.course import Course

router = APIRouter(prefix="/courses", tags=["Courses"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def courses_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    courses = session.exec(select(Course).order_by(Course.id)).all()
    selected_id = request.cookies.get("selected_course_id")
    return templates.TemplateResponse(request=request, name="courses/index.html", context={"user": user, "courses": courses, "selected_id": int(selected_id) if selected_id and selected_id.isdigit() else None})


@router.post("/select")
def select_course(request: Request, course_id: int = Form(...), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    course = session.get(Course, course_id)
    if not user or not course:
        return RedirectResponse("/courses", status_code=303)
    response = RedirectResponse(f"/dashboard?course_id={course.id}", status_code=303)
    response.set_cookie("selected_course_id", str(course.id), httponly=True, samesite="lax")
    return response
