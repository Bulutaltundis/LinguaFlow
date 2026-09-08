from datetime import datetime, timezone
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.api_auth import get_api_user
from app.core.database import get_session
from app.models.lesson import Question
from app.models.question_progress import UserQuestionProgress
from app.models.user import User


router = APIRouter(prefix="/api/learning", tags=["learning"])


# ---------------------------------------------------------
# Soru ekleme
# ---------------------------------------------------------

@router.post("/questions")
def create_question(
    data: dict,
    user: User = Depends(get_api_user),
    session: Session = Depends(get_session),
):
    # Şimdilik sadece admin ekleyebilsin
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Bu işlem için admin yetkisi gerekiyor.",
        )

    level = str(data.get("level", "")).strip().upper()
    prompt = str(data.get("prompt", "")).strip()
    answer = str(data.get("answer", "")).strip()

    if not level or not prompt or not answer:
        raise HTTPException(
            status_code=400,
            detail="level, prompt ve answer zorunludur.",
        )

    question = Question(
        level=level,
        type=str(data.get("type", "multiple_choice")),
        prompt=prompt,
        answer=answer,
        options=str(data.get("options", "")),
        explanation=str(data.get("explanation", "")),
        audio_url=str(data.get("audio_url", "")),
        words=str(data.get("words", "")),
        lesson_id=data.get("lesson_id"),
    )

    session.add(question)
    session.commit()
    session.refresh(question)

    return {
        "id": question.id,
        "level": question.level,
        "type": question.type,
        "prompt": question.prompt,
        "answer": question.answer,
    }


# ---------------------------------------------------------
# Kullanıcı için sonraki ders
# ---------------------------------------------------------

@router.get("/next")
def get_next_questions(
    limit: int = 10,
    user: User = Depends(get_api_user),
    session: Session = Depends(get_session),
):
    limit = max(1, min(limit, 20))

    # Kullanıcının seviyesi.
    # User modelinde level alanı yoksa şimdilik A1 kullanıyoruz.
    user_level = getattr(user, "level", None) or "A1"
    user_level = user_level.upper()

    questions = session.exec(
        select(Question)
        .where(Question.level == user_level)
    ).all()

    if not questions:
        return {
            "level": user_level,
            "questions": [],
        }

    # Kullanıcının mevcut ilerlemelerini al
    question_ids = [q.id for q in questions if q.id is not None]

    progress_rows = session.exec(
        select(UserQuestionProgress)
        .where(
            UserQuestionProgress.user_id == user.id,
            UserQuestionProgress.question_id.in_(question_ids),
        )
    ).all()

    progress_map = {
        row.question_id: row
        for row in progress_rows
    }

    weighted_questions = []

    for question in questions:
        if question.id is None:
            continue

        progress = progress_map.get(question.id)

        if progress is None:
            # Yeni soru
            weight = 5.0
        else:
            mastery = max(0.0, min(progress.mastery, 1.0))

            # Mastery düşükse soru daha sık gelsin.
            weight = 1.0 + ((1.0 - mastery) * 9.0)

            # Son cevap yanlışsa ekstra ağırlık.
            if progress.last_answer_correct is False:
                weight += 4.0

        weighted_questions.append(
            (question, weight)
        )

    # Weighted random selection
    selected = []

    pool = weighted_questions.copy()

    while pool and len(selected) < limit:
        questions_only = [item[0] for item in pool]
        weights = [item[1] for item in pool]

        chosen = random.choices(
            questions_only,
            weights=weights,
            k=1,
        )[0]

        selected.append(chosen)

        pool = [
            item
            for item in pool
            if item[0].id != chosen.id
        ]

    return {
        "level": user_level,
        "count": len(selected),
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "prompt": q.prompt,
                "options": q.options,
                "audio_url": q.audio_url,
                "words": q.words,
            }
            for q in selected
        ],
    }


# ---------------------------------------------------------
# Cevap gönderme
# ---------------------------------------------------------

@router.post("/answer")
def answer_question(
    data: dict,
    user: User = Depends(get_api_user),
    session: Session = Depends(get_session),
):
    question_id = data.get("question_id")
    user_answer = str(data.get("answer", "")).strip()

    if not question_id:
        raise HTTPException(
            status_code=400,
            detail="question_id zorunludur.",
        )

    question = session.get(Question, int(question_id))

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Soru bulunamadı.",
        )

    correct_answer = question.answer.strip()

    correct = (
        user_answer.casefold()
        == correct_answer.casefold()
    )

    progress = session.exec(
        select(UserQuestionProgress)
        .where(
            UserQuestionProgress.user_id == user.id,
            UserQuestionProgress.question_id == question.id,
        )
    ).first()

    if progress is None:
        progress = UserQuestionProgress(
            user_id=user.id,
            question_id=question.id,
        )

    progress.attempts += 1

    if correct:
        progress.correct_count += 1
        progress.mastery += 0.15
    else:
        progress.incorrect_count += 1
        progress.mastery -= 0.20

    progress.mastery = max(
        0.0,
        min(progress.mastery, 1.0),
    )

    progress.last_answer_correct = correct
    progress.updated_at = datetime.now(timezone.utc)

    session.add(progress)
    session.commit()
    session.refresh(progress)

    return {
        "correct": correct,
        "correct_answer": question.answer,
        "explanation": question.explanation,
        "mastery": progress.mastery,
        "attempts": progress.attempts,
    }