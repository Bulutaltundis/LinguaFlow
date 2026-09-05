from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import hash_password, verify_password
from app.models.user import User


templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={},
    )


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("student"),
    session: Session = Depends(get_session),
):
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "Kullanıcı adı en az 3 karakter olmalı.",
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "Şifre en az 8 karakter olmalı.",
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    existing_user = session.exec(
        select(User).where(
            (User.username == username)
            | (User.email == email)
        )
    ).first()

    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "Bu kullanıcı adı veya e-posta zaten kullanılıyor.",
                "username": username,
                "email": email,
            },
            status_code=400,
        )

    if role not in {"student", "teacher"}:
        role = "student"

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    response = RedirectResponse(
        url="/dashboard",
        status_code=303,
    )

    response.set_cookie(
        key="session_user_id",
        value=str(user.id),
        httponly=True,
        samesite="lax",
    )

    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={},
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    email = email.strip().lower()

    user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if not user or not verify_password(
        password,
        user.password_hash,
    ):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "E-posta veya şifre hatalı.",
                "email": email,
            },
            status_code=401,
        )

    response = RedirectResponse(
        url="/dashboard",
        status_code=303,
    )

    response.set_cookie(
        key="session_user_id",
        value=str(user.id),
        httponly=True,
        samesite="lax",
    )

    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(
        url="/",
        status_code=303,
    )

    response.delete_cookie("session_user_id")

    return response
