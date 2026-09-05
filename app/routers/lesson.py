import random
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.lesson import Lesson, Question
from app.models.progress import UserProgress
from app.models.user import User
from app.models.xp_event import XPEvent
from app.core.activity import register_activity


templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/lesson",
    tags=["Lessons"],
)


def get_current_user(
    request: Request,
    session: Session,
):
    user_id = request.cookies.get("session_user_id")

    if not user_id:
        return None

    try:
        user_id = int(user_id)
    except ValueError:
        return None

    return session.get(User, user_id)


def prepare_question(question: Question):
    """
    Sorunun tipine göre öğrenci ekranında kullanılacak
    options ve words listelerini hazırlar.
    """

    options = []
    words = []

    if question.type == "multiple_choice":
        if question.options:
            options = [
                option.strip()
                for option in question.options.split("|")
                if option.strip()
            ]

            random.shuffle(options)

    elif question.type == "word_order":
        if question.words:
            words = [
                word.strip()
                for word in question.words.split("|")
                if word.strip()
            ]

            random.shuffle(words)

    return options, words


@router.get(
    "/{lesson_id}",
    response_class=HTMLResponse,
)
def lesson_page(
    lesson_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    if not user:
        return RedirectResponse(
            "/auth/login",
            status_code=303,
        )

    if user.hearts <= 0:
        return RedirectResponse("/shop?error=no_hearts", status_code=303)

    register_activity(user, session)

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

    if not questions:
        return HTMLResponse(
            "Bu derste soru yok.",
            status_code=404,
        )

    question = questions[0]

    options, words = prepare_question(question)

    return templates.TemplateResponse(
        request=request,
        name="lesson/index.html",
        context={
            "user": user,
            "lesson": lesson,
            "question": question,
            "question_index": 0,
            "total": len(questions),
            "options": options,
            "words": words,
            "result": None,
        },
    )


@router.post(
    "/{lesson_id}/answer",
    response_class=HTMLResponse,
)
def answer_question(
    lesson_id: int,
    request: Request,
    question_id: int = Form(...),
    answer: str = Form(...),
    question_index: int = Form(...),
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    if not user:
        return RedirectResponse(
            "/auth/login",
            status_code=303,
        )

    if user.hearts <= 0:
        return RedirectResponse("/shop?error=no_hearts", status_code=303)

    lesson = session.get(Lesson, lesson_id)
    question = session.get(Question, question_id)

    if not lesson:
        return HTMLResponse(
            "Ders bulunamadı.",
            status_code=404,
        )

    if not question:
        return HTMLResponse(
            "Soru bulunamadı.",
            status_code=404,
        )

    # Sorunun gerçekten bu derse ait olduğunu kontrol et.
    if question.lesson_id != lesson_id:
        return HTMLResponse(
            "Geçersiz soru.",
            status_code=400,
        )

    questions = session.exec(
        select(Question)
        .where(Question.lesson_id == lesson_id)
        .order_by(Question.order)
    ).all()

    if not questions:
        return HTMLResponse(
            "Bu derste soru yok.",
            status_code=404,
        )

    # question_index'in geçerli olduğundan emin ol.
    if question_index < 0 or question_index >= len(questions):
        return HTMLResponse(
            "Geçersiz soru sırası.",
            status_code=400,
        )

    # Gönderilen question_id'nin gerçekten o sıradaki soru olduğunu kontrol et.
    current_question = questions[question_index]

    if current_question.id != question.id:
        return HTMLResponse(
            "Geçersiz soru.",
            status_code=400,
        )

    # Cevabı normalize et.
    user_answer = normalize_answer(answer)
    correct_answer = normalize_answer(question.answer)

    print("================================")
    print("QUESTION TYPE:", question.type)
    print("USER ANSWER:", repr(answer))
    print("NORMALIZED USER:", repr(user_answer))
    print("CORRECT ANSWER:", repr(question.answer))
    print("NORMALIZED CORRECT:", repr(correct_answer))

    if question.type == "word_order":

        # Noktalama işaretlerini kaldır
        user_clean = re.sub(r"[^\w\s]", "", user_answer)
        correct_clean = re.sub(r"[^\w\s]", "", correct_answer)

        # Kelimelere ayır
        user_words = user_clean.split()
        correct_words = correct_clean.split()

        print("USER WORDS:", user_words)
        print("CORRECT WORDS:", correct_words)

        correct = user_words == correct_words

    else:

        correct = user_answer == correct_answer

    print("RESULT:", correct)
    print("================================")

    xp_earned = 0

    if correct:
        xp_earned = lesson.xp_reward
        boost_until = user.xp_boost_until
        if boost_until and boost_until.tzinfo is None:
            boost_until = boost_until.replace(tzinfo=timezone.utc)
        if boost_until and boost_until > datetime.now(timezone.utc):
            xp_earned *= 2
        user.xp += xp_earned

        session.add(
            XPEvent(
                user_id=user.id,
                amount=xp_earned,
                source="lesson",
            )
        )       
    else:
        user.hearts = max(0, user.hearts - 1)

    session.add(user)
    session.commit()
    session.refresh(user)

    next_index = question_index + 1
    finished = next_index >= len(questions)

    if finished:
        progress = session.exec(
            select(UserProgress)
            .where(
                (UserProgress.user_id == user.id)
                & (UserProgress.lesson_id == lesson_id)
            )
        ).first()

        if not progress:
            progress = UserProgress(
                user_id=user.id,
                lesson_id=lesson_id,
                completed=True,
                score=xp_earned,
            )
            session.add(progress)
        else:
            progress.completed = True

        session.commit()

        return templates.TemplateResponse(
            request=request,
            name="lesson/result.html",
            context={
                "user": user,
                "lesson": lesson,
                "correct": correct,
                "xp_earned": xp_earned,
                "total": len(questions),
            },
        )

    next_question = questions[next_index]

    options, words = prepare_question(next_question)

    return templates.TemplateResponse(
        request=request,
        name="lesson/index.html",
        context={
            "user": user,
            "lesson": lesson,
            "question": next_question,
            "question_index": next_index,
            "total": len(questions),
            "options": options,
            "words": words,
            "result": {
                "correct": correct,
                "message": (
                    "Harika! Doğru cevap 🎉"
                    if correct
                    else f"Doğru cevap: {question.answer}"
                ),
                "xp": xp_earned,
            },
        },
    )

def normalize_answer(value: str) -> str:
    """
    Cevapları karşılaştırmadan önce normalize eder.
    Büyük/küçük harf, fazla boşluk ve noktalama problemlerini çözer.
    """
    if not value:
        return ""

    value = value.strip().lower()

    # Fazla boşlukları temizle
    value = re.sub(r"\s+", " ", value)

    return value
