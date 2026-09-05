import os
import uuid
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    UploadFile,
    File,
)


from app.core.database import get_session
from app.models.course import Course
from app.models.lesson import Unit, Lesson, Question
from app.models.user import User
from app.models.shop import ShopItem

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


def current_user(request: Request, session: Session):
    user_id = request.cookies.get("session_user_id")

    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except ValueError:
        return None

    return session.get(User, user_id)


def require_admin(request: Request, session: Session):
    user = current_user(request, session)

    if not user or not user.is_admin:
        return None

    return user


@router.post("/users/{user_id}/make-teacher")
def make_teacher(user_id: int, request: Request, session: Session = Depends(get_session)):
    admin = require_admin(request, session)
    target = session.get(User, user_id)
    if not admin or not target:
        return RedirectResponse("/admin", status_code=303)
    target.role = "teacher"
    session.add(target)
    session.commit()
    return RedirectResponse("/admin?success=teacher", status_code=303)


@router.get("", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    courses = session.exec(select(Course)).all()
    units = session.exec(select(Unit)).all()
    lessons = session.exec(select(Lesson)).all()
    questions = session.exec(select(Question)).all()
    users = session.exec(select(User)).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={
            "user": user,
            "courses": courses,
            "units": units,
            "lessons": lessons,
            "questions": questions,
            "users": users,
        },
    )


@router.get("/courses", response_class=HTMLResponse)
def courses_page(
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    courses = session.exec(
        select(Course).order_by(Course.id)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/courses.html",
        context={
            "user": user,
            "courses": courses,
        },
    )


@router.post("/courses/create")
def create_course(
    request: Request,
    name: str = Form(...),
    language: str = Form(...),
    description: str = Form(""),
    icon: str = Form("🌍"),
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    course = Course(
        name=name.strip(),
        language=language.strip(),
        description=description.strip(),
        icon=icon.strip() or "🌍",
    )

    session.add(course)
    session.commit()

    return RedirectResponse(
        "/admin/courses",
        status_code=303,
    )


@router.get("/courses/{course_id}", response_class=HTMLResponse)
def course_page(
    course_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    course = session.get(Course, course_id)

    if not course:
        return HTMLResponse(
            "Kurs bulunamadı.",
            status_code=404,
        )

    units = session.exec(
        select(Unit)
        .where(Unit.course_id == course_id)
        .order_by(Unit.order)
    ).all()

    lessons = session.exec(
        select(Lesson)
        .join(Unit)
        .where(Unit.course_id == course_id)
        .order_by(Lesson.order)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/course.html",
        context={
            "user": user,
            "course": course,
            "units": units,
            "lessons": lessons,
        },
    )


@router.post("/courses/{course_id}/units/create")
def create_unit(
    course_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    order: int = Form(0),
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    course = session.get(Course, course_id)

    if not course:
        return HTMLResponse(
            "Kurs bulunamadı.",
            status_code=404,
        )

    unit = Unit(
        course_id=course_id,
        title=title.strip(),
        description=description.strip(),
        order=order,
    )

    session.add(unit)
    session.commit()

    return RedirectResponse(
        f"/admin/courses/{course_id}",
        status_code=303,
    )


@router.get("/units/{unit_id}", response_class=HTMLResponse)
def unit_page(
    unit_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    unit = session.get(Unit, unit_id)

    if not unit:
        return HTMLResponse(
            "Unit bulunamadı.",
            status_code=404,
        )

    lessons = session.exec(
        select(Lesson)
        .where(Lesson.unit_id == unit_id)
        .order_by(Lesson.order)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/unit.html",
        context={
            "user": user,
            "unit": unit,
            "lessons": lessons,
        },
    )


@router.post("/units/{unit_id}/lessons/create")
def create_lesson(
    unit_id: int,
    request: Request,
    title: str = Form(...),
    icon: str = Form("📖"),
    xp_reward: int = Form(10),
    order: int = Form(0),
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    unit = session.get(Unit, unit_id)

    if not unit:
        return HTMLResponse(
            "Unit bulunamadı.",
            status_code=404,
        )

    lesson = Lesson(
        unit_id=unit_id,
        title=title.strip(),
        icon=icon.strip() or "📖",
        xp_reward=xp_reward,
        order=order,
    )

    session.add(lesson)
    session.commit()

    return RedirectResponse(
        f"/admin/units/{unit_id}",
        status_code=303,
    )


@router.get("/lessons/{lesson_id}", response_class=HTMLResponse)
def lesson_page(
    lesson_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    lesson = session.get(Lesson, lesson_id)

    if not lesson:
        return HTMLResponse(
            "Ders bulunamadı.",
            status_code=404,
        )

    questions = session.exec(
        select(Question)
        .where(Question.lesson_id == lesson_id)
        .order_by(Question.order)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/lesson.html",
        context={
            "user": user,
            "lesson": lesson,
            "questions": questions,
        },
    )


@router.post("/lessons/{lesson_id}/questions/create")
async def create_question(
    lesson_id: int,
    request: Request,

    type: str = Form(...),
    prompt: str = Form(...),

    answer: str = Form(""),

    translation_answer: str = Form(""),
    fill_blank_answer: str = Form(""),
    word_order_answer: str = Form(""),
    listening_answer: str = Form(""),

    correct_option: int | None = Form(None),

    options: list[str] = Form([]),
    words: str = Form(""),

    explanation: str = Form(""),
    order: int = Form(0),

    audio: UploadFile | None = File(None),

    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse(
            "/",
            status_code=303,
        )

    lesson = session.get(Lesson, lesson_id)

    if not lesson:
        return HTMLResponse(
            "Ders bulunamadı.",
            status_code=404,
        )

    question_type = type.strip()

    # --------------------------------
    # MULTIPLE CHOICE OPTIONS
    # --------------------------------

    clean_options = [
        option.strip()
        for option in options
        if option.strip()
    ]

    options_text = "|".join(clean_options)

    # --------------------------------
    # WORD ORDER
    # --------------------------------

    clean_words = [
        word.strip()
        for word in words.split("|")
        if word.strip()
    ]

    words_text = "|".join(clean_words)

    # --------------------------------
    # DOĞRU CEVABI BELİRLE
    # --------------------------------

    if question_type == "multiple_choice":

        if not clean_options:
            return HTMLResponse(
                "En az bir seçenek eklemelisin.",
                status_code=400,
            )

        if correct_option is None:
            return HTMLResponse(
                "Çoktan seçmeli sorularda doğru cevap seçilmelidir.",
                status_code=400,
            )

        if correct_option < 0 or correct_option >= len(clean_options):
            return HTMLResponse(
                "Geçersiz doğru cevap seçimi.",
                status_code=400,
            )

        final_answer = clean_options[correct_option]

    elif question_type == "translation":

        final_answer = translation_answer.strip()

    elif question_type == "fill_blank":

        final_answer = fill_blank_answer.strip()

    elif question_type == "word_order":

        final_answer = word_order_answer.strip()

    elif question_type == "listening":

        final_answer = listening_answer.strip()

    else:

        final_answer = answer.strip()

    # --------------------------------
    # AUDIO
    # --------------------------------

    audio_url = ""

    if audio and audio.filename:

        extension = os.path.splitext(
            audio.filename
        )[1].lower()

        allowed = {
            ".mp3",
            ".wav",
            ".m4a",
            ".ogg",
        }

        if extension not in allowed:
            return HTMLResponse(
                "Desteklenmeyen ses formatı.",
                status_code=400,
            )

        filename = (
            f"{uuid.uuid4().hex}{extension}"
        )

        audio_dir = "app/static/audio"

        os.makedirs(
            audio_dir,
            exist_ok=True,
        )

        filepath = os.path.join(
            audio_dir,
            filename,
        )

        content = await audio.read()

        with open(filepath, "wb") as file:
            file.write(content)

        audio_url = f"/static/audio/{filename}"

    # --------------------------------
    # CREATE QUESTION
    # --------------------------------

    question = Question(
        lesson_id=lesson_id,
        type=question_type,
        prompt=prompt.strip(),

        # Her soru tipinin gerçek cevabı
        # burada Question.answer'a kaydedilir.
        answer=final_answer,

        options=options_text,
        words=words_text,
        explanation=explanation.strip(),
        audio_url=audio_url,
        order=order,
    )

    session.add(question)
    session.commit()

    return RedirectResponse(
        f"/admin/lessons/{lesson_id}",
        status_code=303,
    )

# ============================================================
# SHOP MANAGEMENT
# ============================================================

@router.get("/shop", response_class=HTMLResponse)
def admin_shop(
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    items = session.exec(
        select(ShopItem)
        .order_by(ShopItem.id)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/shop.html",
        context={
            "user": user,
            "items": items,
        },
    )


@router.post("/shop/create")
def admin_create_shop_item(
    request: Request,

    name: str = Form(...),
    description: str = Form(""),
    icon: str = Form("🎁"),
    price: int = Form(...),
    type: str = Form(...),

    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    name = name.strip()
    description = description.strip()
    icon = icon.strip() or "🎁"
    type = type.strip()

    if not name:
        return RedirectResponse(
            "/admin/shop?error=invalid_name",
            status_code=303,
        )

    if price < 0:
        return RedirectResponse(
            "/admin/shop?error=invalid_price",
            status_code=303,
        )

    allowed_types = {
        "heart",
        "heart_pack",
        "streak_freeze",
        "xp_boost",
        "avatar",
        "theme",
        "cosmetic",
    }

    if type not in allowed_types:
        return RedirectResponse(
            "/admin/shop?error=invalid_type",
            status_code=303,
        )

    item = ShopItem(
        name=name,
        description=description,
        icon=icon,
        price=price,
        type=type,
        active=True,
    )

    session.add(item)
    session.commit()

    return RedirectResponse(
        "/admin/shop?success=created",
        status_code=303,
    )


@router.post("/shop/{item_id}/edit")
def admin_edit_shop_item(
    item_id: int,
    request: Request,

    name: str = Form(...),
    description: str = Form(""),
    icon: str = Form("🎁"),
    price: int = Form(...),
    type: str = Form(...),

    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    item = session.get(ShopItem, item_id)

    if not item:
        return HTMLResponse(
            "Mağaza ürünü bulunamadı.",
            status_code=404,
        )

    allowed_types = {
        "heart",
        "heart_pack",
        "streak_freeze",
        "xp_boost",
        "avatar",
        "theme",
        "cosmetic",
    }

    if type not in allowed_types:
        return RedirectResponse(
            "/admin/shop?error=invalid_type",
            status_code=303,
        )

    if price < 0:
        return RedirectResponse(
            "/admin/shop?error=invalid_price",
            status_code=303,
        )

    item.name = name.strip()
    item.description = description.strip()
    item.icon = icon.strip() or "🎁"
    item.price = price
    item.type = type

    session.add(item)
    session.commit()

    return RedirectResponse(
        "/admin/shop?success=updated",
        status_code=303,
    )


@router.post("/shop/{item_id}/toggle")
def admin_toggle_shop_item(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    item = session.get(ShopItem, item_id)

    if not item:
        return HTMLResponse(
            "Mağaza ürünü bulunamadı.",
            status_code=404,
        )

    item.active = not item.active

    session.add(item)
    session.commit()

    return RedirectResponse(
        "/admin/shop?success=toggled",
        status_code=303,
    )


@router.post("/shop/{item_id}/delete")
def admin_delete_shop_item(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = require_admin(request, session)

    if not user:
        return RedirectResponse("/", status_code=303)

    item = session.get(ShopItem, item_id)

    if not item:
        return HTMLResponse(
            "Mağaza ürünü bulunamadı.",
            status_code=404,
        )

    session.delete(item)
    session.commit()

    return RedirectResponse(
        "/admin/shop?success=deleted",
        status_code=303,
    )
