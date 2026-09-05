from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func

from app.core.auth import get_current_user
from app.core.database import get_session

from app.models.user import User
from app.models.progress import UserProgress
from app.models.lesson import Lesson
from app.models.classroom import Classroom, ClassMembership
from app.core.auth import get_current_user
from app.models.shop import ShopItem, Purchase


router = APIRouter(
    tags=["Profile"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


def profile_data(user, session):
    owned = session.exec(select(ShopItem).join(Purchase).where(Purchase.user_id == user.id)).all()
    themes = {"default": "LinguaFlow"}
    cosmetics = ["Yok"]
    for item in owned:
        if item.type == "theme":
            themes["ocean" if "okyanus" in item.name.lower() else item.name.lower().replace(" ", "-")] = item.name
        if item.type in {"cosmetic", "avatar"}:
            cosmetics.append(item.name)
    return themes, cosmetics


@router.get("/profile/settings", response_class=HTMLResponse)
def profile_settings(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    themes, cosmetics = profile_data(user, session)
    return templates.TemplateResponse(request=request, name="profile/settings.html", context={"user": user, "themes": themes, "cosmetics": cosmetics, "avatars": ["🧑‍💻", "🦊", "🐼", "🦉", "🐯", "🐸"]})


@router.post("/profile/settings")
def update_profile(request: Request, avatar: str = Form("🧑‍💻"), theme: str = Form("default"), cosmetic: str = Form(""), session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    themes, cosmetics = profile_data(user, session)
    if avatar not in {"🧑‍💻", "🦊", "🐼", "🦉", "🐯", "🐸"}:
        avatar = "🧑‍💻"
    if theme not in themes:
        theme = "default"
    if cosmetic not in cosmetics:
        cosmetic = ""
    user.avatar, user.theme, user.cosmetic = avatar, theme, "" if cosmetic == "Yok" else cosmetic
    session.add(user)
    session.commit()
    return RedirectResponse("/profile?success=updated", status_code=303)


@router.get("/profile/{profile_id}", response_class=HTMLResponse)
def public_profile(profile_id: int, request: Request, session: Session = Depends(get_session)):
    viewer = get_current_user(request, session)
    viewed = session.get(User, profile_id)
    if not viewer or not viewed:
        return RedirectResponse("/auth/login", status_code=303)
    viewer_rooms = {row.classroom_id for row in session.exec(select(ClassMembership).where(ClassMembership.user_id == viewer.id)).all()}
    viewed_rooms = {row.classroom_id for row in session.exec(select(ClassMembership).where(ClassMembership.user_id == viewed.id)).all()}
    shared = viewer_rooms & viewed_rooms
    if viewer.id != viewed.id and not shared:
        return HTMLResponse("Bu profil yalnızca sınıf arkadaşlarına açıktır.", status_code=403)
    completed = session.exec(select(UserProgress).where((UserProgress.user_id == viewed.id) & (UserProgress.completed == True))).all()
    return templates.TemplateResponse(request=request, name="profile/public.html", context={"user": viewer, "viewed": viewed, "profile_theme": viewed.theme, "completed_count": len(completed)})


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(
        request,
        session,
    )

    if not user:
        return RedirectResponse(
            "/auth/login",
            status_code=303,
        )

    # Tamamlanan dersler
    completed_lessons = session.exec(
        select(UserProgress)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.completed == True,
        )
    ).all()

    completed_count = len(completed_lessons)

    # Toplam ders sayısı
    total_lessons = session.exec(
        select(func.count(Lesson.id))
    ).one()

    # XP progress
    # Her seviye için 100 XP
    xp_in_level = user.xp % 100

    xp_progress = xp_in_level

    # Sonraki level
    xp_to_next = 100 - xp_in_level

    # Basit achievement sistemi
    achievements = [
        {
            "icon": "🔥",
            "name": "İlk Seri",
            "description": "3 günlük seri",
            "unlocked": user.streak >= 3,
        },
        {
            "icon": "⚡",
            "name": "XP Avcısı",
            "description": "100 XP kazan",
            "unlocked": user.xp >= 100,
        },
        {
            "icon": "📚",
            "name": "Öğrenci",
            "description": "5 ders tamamla",
            "unlocked": completed_count >= 5,
        },
        {
            "icon": "🏆",
            "name": "Usta",
            "description": "500 XP kazan",
            "unlocked": user.xp >= 500,
        },
        {
            "icon": "💎",
            "name": "Gem Koleksiyoncusu",
            "description": "500 gem",
            "unlocked": user.gems >= 500,
        },
        {
            "icon": "🚀",
            "name": "Seviye Atla",
            "description": "Seviye 5'e ulaş",
            "unlocked": user.level >= 5,
        },
    ]

    return templates.TemplateResponse(
        request=request,
        name="profile/index.html",
        context={
            "user": user,
            "completed_count": completed_count,
            "total_lessons": total_lessons,
            "xp_progress": xp_progress,
            "xp_to_next": xp_to_next,
            "achievements": achievements,
        },
    )
