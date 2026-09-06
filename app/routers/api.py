import re
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, delete, func, select, update

from app.core.api_auth import create_api_key, get_api_user
from app.core.auth import create_session, cookie_kwargs, CSRF_COOKIE, SESSION_COOKIE
from app.core.billing import has_unlimited_hearts
from app.core.database import get_session
from app.core.security import verify_password
from app.models.api_key import APIKey
from app.models.attempt import QuestionAttempt
from app.models.classroom import Assignment, ClassMembership, Classroom
from app.models.course import Course
from app.models.lesson import Lesson, Question, Unit
from app.models.progress import UserProgress
from app.models.reward import Chest, UserChest, UserTask
from app.models.shop import Purchase, ShopItem
from app.models.user import User
from app.models.xp_event import XPEvent
from app.services.rewards import claim_task, ensure_daily_tasks, update_task


router = APIRouter(prefix="/api", tags=["Mobile API"])


def iso(value):
    return value.isoformat() if value else None


def user_json(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "avatar": user.avatar,
        "theme": user.theme,
        "cosmetic": user.cosmetic,
        "xp": user.xp,
        "level": user.level,
        "gems": user.gems,
        "hearts": None if has_unlimited_hearts(user) else user.hearts,
        "unlimited_hearts": has_unlimited_hearts(user),
        "streak": user.streak,
        "subscription_plan": user.subscription_plan,
        "subscription_status": user.subscription_status,
    }


def course_json(course: Course):
    return {"id": course.id, "name": course.name, "language": course.language, "description": course.description, "icon": course.icon}


def question_json(question: Question, include_answer: bool = False):
    data = {
        "id": question.id,
        "type": question.type,
        "prompt": question.prompt,
        "options": [item.strip() for item in question.options.split("|") if item.strip()],
        "words": [item.strip() for item in question.words.split("|") if item.strip()],
        "order": question.order,
    }
    if include_answer:
        data["answer"] = question.answer
        data["explanation"] = question.explanation
    return data


@router.post("/auth/login")
async def api_login(request: Request, session: Session = Depends(get_session)):
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")
    key = create_api_key(user, session)
    return {"api_key": key, "token_type": "ApiKey", "user": user_json(user)}


@router.post("/auth/key/rotate")
def rotate_api_key(user: User = Depends(get_api_user), session: Session = Depends(get_session)):
    for key in session.exec(select(APIKey).where((APIKey.user_id == user.id) & (APIKey.revoked_at == None))).all():
        key.revoked_at = datetime.now(timezone.utc)
        session.add(key)
    session.commit()
    return {"api_key": create_api_key(user, session), "token_type": "ApiKey"}


@router.get("/me")
def me(user: User = Depends(get_api_user)):
    return {"user": user_json(user)}


@router.get("/courses")
def courses(session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    return {"courses": [course_json(item) for item in session.exec(select(Course).order_by(Course.id)).all()]}


@router.get("/courses/{course_id}")
def course_detail(course_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Kurs bulunamadı")
    units = session.exec(select(Unit).where(Unit.course_id == course_id).order_by(Unit.order)).all()
    return {"course": course_json(course), "units": [{
        "id": unit.id,
        "title": unit.title,
        "description": unit.description,
        "order": unit.order,
        "lessons": [{"id": lesson.id, "title": lesson.title, "icon": lesson.icon, "xp_reward": lesson.xp_reward, "order": lesson.order}
                    for lesson in session.exec(select(Lesson).where(Lesson.unit_id == unit.id).order_by(Lesson.order)).all()],
    } for unit in units]}


@router.get("/dashboard")
def dashboard(course_id: int | None = None, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    course = session.get(Course, course_id) if course_id else session.exec(select(Course).order_by(Course.id)).first()
    units = []
    completed_count = 0
    total_count = 0
    if course:
        for unit in session.exec(select(Unit).where(Unit.course_id == course.id).order_by(Unit.order)).all():
            lessons = []
            for lesson in session.exec(select(Lesson).where(Lesson.unit_id == unit.id).order_by(Lesson.order)).all():
                progress = session.exec(select(UserProgress).where((UserProgress.user_id == user.id) & (UserProgress.lesson_id == lesson.id))).first()
                completed = bool(progress and progress.completed)
                completed_count += int(completed)
                total_count += 1
                lessons.append({"id": lesson.id, "title": lesson.title, "icon": lesson.icon, "xp_reward": lesson.xp_reward, "completed": completed, "score": progress.score if progress else 0})
            units.append({"id": unit.id, "title": unit.title, "description": unit.description, "lessons": lessons})
    return {"user": user_json(user), "course": course_json(course) if course else None, "units": units, "completed_lessons": completed_count, "total_lessons": total_count}


@router.get("/leaderboard")
def api_leaderboard(class_id: int | None = None, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    week_start = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    member_ids = None
    if class_id:
        room = session.get(Classroom, class_id)
        if not room or (room.teacher_id != user.id and not session.exec(select(ClassMembership).where((ClassMembership.classroom_id == class_id) & (ClassMembership.user_id == user.id))).first()):
            raise HTTPException(403, "Bu sınıf leaderboard'una erişim yok")
        member_ids = [room.teacher_id] + [m.user_id for m in session.exec(select(ClassMembership).where(ClassMembership.classroom_id == class_id)).all()]
    statement = select(XPEvent.user_id, func.sum(XPEvent.amount).label("weekly_xp")).where(XPEvent.created_at >= week_start).group_by(XPEvent.user_id).order_by(func.sum(XPEvent.amount).desc())
    if member_ids is not None:
        statement = statement.where(XPEvent.user_id.in_(member_ids))
    entries = []
    for position, row in enumerate(session.exec(statement).all(), start=1):
        ranked_user = session.get(User, row.user_id)
        if ranked_user:
            entries.append({"position": position, "xp": row.weekly_xp or 0, "user": {"id": ranked_user.id, "username": ranked_user.username, "avatar": ranked_user.avatar, "level": ranked_user.level}})
    return {"week_start": iso(week_start), "leaderboard": entries}


@router.get("/profile")
def own_profile(session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    completed = len(session.exec(select(UserProgress).where((UserProgress.user_id == user.id) & (UserProgress.completed == True))).all())
    total = session.exec(select(func.count(Lesson.id))).one()
    return {"user": user_json(user), "completed_lessons": completed, "total_lessons": total}


@router.get("/profile/{profile_id}")
def public_profile(profile_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    viewed = session.get(User, profile_id)
    if not viewed:
        raise HTTPException(404, "Profil bulunamadı")
    viewer_rooms = {row.classroom_id for row in session.exec(select(ClassMembership).where(ClassMembership.user_id == user.id)).all()}
    viewed_rooms = {row.classroom_id for row in session.exec(select(ClassMembership).where(ClassMembership.user_id == viewed.id)).all()}
    if user.id != viewed.id and not viewer_rooms.intersection(viewed_rooms):
        raise HTTPException(403, "Bu profil yalnızca sınıf arkadaşlarına açıktır")
    completed = len(session.exec(select(UserProgress).where((UserProgress.user_id == viewed.id) & (UserProgress.completed == True))).all())
    return {"profile": {"id": viewed.id, "username": viewed.username, "avatar": viewed.avatar, "theme": viewed.theme, "cosmetic": viewed.cosmetic, "xp": viewed.xp, "level": viewed.level, "streak": viewed.streak, "completed_lessons": completed}}


@router.put("/profile/settings")
async def profile_settings(request: Request, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    body = await request.json()
    avatar = body.get("avatar", user.avatar)
    theme = body.get("theme", user.theme)
    cosmetic = body.get("cosmetic", user.cosmetic)
    if avatar not in {"🧑‍💻", "🦊", "🐼", "🦉", "🐯", "🐸"}:
        raise HTTPException(400, "Geçersiz avatar")
    user.avatar, user.theme, user.cosmetic = str(avatar), str(theme), str(cosmetic)
    session.add(user)
    session.commit()
    return {"user": user_json(user)}


@router.get("/lessons/{lesson_id}")
def lesson_detail(lesson_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    lesson = session.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(404, "Ders bulunamadı")
    progress = session.exec(select(UserProgress).where((UserProgress.user_id == user.id) & (UserProgress.lesson_id == lesson_id))).first()
    questions = session.exec(select(Question).where(Question.lesson_id == lesson_id).order_by(Question.order)).all()
    return {"lesson": {"id": lesson.id, "title": lesson.title, "icon": lesson.icon, "xp_reward": lesson.xp_reward, "completed": bool(progress and progress.completed)}, "questions": [question_json(q) for q in questions]}


@router.post("/lessons/{lesson_id}/answer")
async def answer_lesson(lesson_id: int, request: Request, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    if not has_unlimited_hearts(user) and user.hearts <= 0:
        raise HTTPException(400, "Yeterli heart yok")
    body = await request.json()
    question_id = int(body.get("question_id", 0))
    question_index = int(body.get("question_index", -1))
    answer = str(body.get("answer", ""))[:500]
    lesson = session.get(Lesson, lesson_id)
    question = session.get(Question, question_id)
    questions = session.exec(select(Question).where(Question.lesson_id == lesson_id).order_by(Question.order)).all()
    if not lesson or not question or question.lesson_id != lesson_id or question_index < 0 or question_index >= len(questions) or questions[question_index].id != question.id:
        raise HTTPException(400, "Geçersiz ders sorusu")
    if session.exec(select(QuestionAttempt).where((QuestionAttempt.user_id == user.id) & (QuestionAttempt.lesson_id == lesson_id) & (QuestionAttempt.question_index == question_index))).first():
        raise HTTPException(409, "Bu soru daha önce cevaplandı")
    normalize = lambda value: re.sub(r"\s+", " ", value.strip().lower())
    correct = normalize(answer) == normalize(question.answer)
    xp_earned = lesson.xp_reward if correct else 0
    boost_until = user.xp_boost_until
    if boost_until and boost_until.tzinfo is None:
        boost_until = boost_until.replace(tzinfo=timezone.utc)
    if correct and boost_until and boost_until > datetime.now(timezone.utc):
        xp_earned *= 2
    session.add(QuestionAttempt(user_id=user.id, lesson_id=lesson_id, question_id=question.id, question_index=question_index, answer=answer, correct=correct))
    if correct:
        user.xp += xp_earned
        session.add(XPEvent(user_id=user.id, amount=xp_earned, source="lesson"))
        update_task(user.id, "questions", 1, session)
        update_task(user.id, "xp", xp_earned, session)
    elif not has_unlimited_hearts(user):
        user.hearts = max(0, user.hearts - 1)
    session.add(user)
    finished = question_index + 1 >= len(questions)
    if finished:
        update_task(user.id, "lesson", 1, session)
        progress = session.exec(select(UserProgress).where((UserProgress.user_id == user.id) & (UserProgress.lesson_id == lesson_id))).first()
        if not progress:
            session.add(UserProgress(user_id=user.id, lesson_id=lesson_id, completed=True, score=xp_earned))
        else:
            progress.completed = True
    session.commit()
    return {"correct": correct, "xp_earned": xp_earned, "finished": finished, "next_question_index": None if finished else question_index + 1, "user": user_json(user)}


@router.get("/shop")
def shop(class_id: int | None = None, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    allowed_class = None
    if class_id:
        room = session.get(Classroom, class_id)
        if room and (room.teacher_id == user.id or session.exec(select(ClassMembership).where((ClassMembership.classroom_id == class_id) & (ClassMembership.user_id == user.id))).first()):
            allowed_class = class_id
    statement = select(ShopItem).where(ShopItem.active == True)
    statement = statement.where((ShopItem.class_id == None) | (ShopItem.class_id == allowed_class)) if allowed_class else statement.where(ShopItem.class_id == None)
    return {"items": [{"id": i.id, "name": i.name, "description": i.description, "icon": i.icon, "price": i.price, "type": i.type, "class_id": i.class_id} for i in session.exec(statement).all()]}


@router.post("/shop/buy/{item_id}")
def buy(item_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    item = session.get(ShopItem, item_id)
    room = session.get(Classroom, item.class_id) if item and item.class_id else None
    if not item or not item.active or (item.class_id and (not room or not (room.teacher_id == user.id or session.exec(select(ClassMembership).where((ClassMembership.classroom_id == item.class_id) & (ClassMembership.user_id == user.id))).first()))):
        raise HTTPException(404, "Mağaza ürünü bulunamadı")
    debit = session.exec(update(User).where((User.id == user.id) & (User.gems >= item.price)).values(gems=User.gems - item.price))
    if debit.rowcount != 1:
        session.rollback()
        raise HTTPException(400, "Yeterli gem yok")
    if item.type == "streak_freeze": user.streak_freezes += 1
    elif item.type == "heart": user.hearts = user.hearts + 1 if has_unlimited_hearts(user) else min(5, user.hearts + 1)
    elif item.type == "heart_pack": user.hearts = user.hearts + 5 if has_unlimited_hearts(user) else min(5, user.hearts + 5)
    elif item.type == "xp_boost":
        now = datetime.now(timezone.utc)
        current_until = user.xp_boost_until
        if current_until and current_until.tzinfo is None:
            current_until = current_until.replace(tzinfo=timezone.utc)
        user.xp_boost_until = max(current_until or now, now) + timedelta(hours=2)
    elif item.type == "theme": user.theme = "ocean" if "okyanus" in item.name.lower() else item.name.lower().replace(" ", "-")
    elif item.type in {"cosmetic", "avatar"}: user.cosmetic = item.name
    else: session.rollback(); raise HTTPException(400, "Geçersiz ürün")
    session.add_all([user, Purchase(user_id=user.id, item_id=item.id)])
    session.commit()
    return {"ok": True, "user": user_json(user)}


@router.get("/rewards")
def rewards(session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    ensure_daily_tasks(user.id, session)
    tasks = session.exec(select(UserTask).where((UserTask.user_id == user.id) & (UserTask.task_date == date.today()))).all()
    chests = []
    for owned in session.exec(select(UserChest).where((UserChest.user_id == user.id) & (UserChest.quantity > 0))).all():
        chest = session.get(Chest, owned.chest_id)
        chests.append({"id": chest.id, "name": chest.name, "rarity": chest.rarity, "icon": chest.icon, "quantity": owned.quantity})
    return {"tasks": [{"id": t.id, "title": t.title, "description": t.description, "target": t.target, "progress": t.progress, "reward_gems": t.reward_gems, "completed": t.completed} for t in tasks], "chests": chests, "user": user_json(user)}


@router.post("/rewards/tasks/{task_id}/claim")
def claim_reward(task_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    if not claim_task(user.id, task_id, session):
        raise HTTPException(400, "Görev ödülü alınamadı")
    return {"ok": True, "user": user_json(user)}


@router.post("/rewards/chests/{chest_id}/open")
def open_reward_chest(chest_id: int, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    chest = session.get(Chest, chest_id)
    if not chest:
        raise HTTPException(404, "Sandık bulunamadı")
    result = session.exec(update(UserChest).where((UserChest.user_id == user.id) & (UserChest.chest_id == chest_id) & (UserChest.quantity > 0)).values(quantity=UserChest.quantity - 1))
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(400, "Bu sandıktan yok")
    gems = secrets.randbelow(chest.max_gems - chest.min_gems + 1) + chest.min_gems
    session.exec(update(User).where(User.id == user.id).values(gems=User.gems + gems))
    session.commit()
    return {"ok": True, "rarity": chest.rarity, "gems": gems, "user": user_json(user)}


@router.get("/classes")
def classes(session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    rooms = session.exec(select(Classroom).where((Classroom.teacher_id == user.id) | Classroom.id.in_(select(ClassMembership.classroom_id).where(ClassMembership.user_id == user.id))).order_by(Classroom.id.desc())).all()
    return {"classes": [{"id": room.id, "name": room.name, "code": room.code if room.teacher_id == user.id else None, "teacher_id": room.teacher_id, "course_id": room.course_id, "member_count": len(session.exec(select(ClassMembership).where(ClassMembership.classroom_id == room.id)).all())} for room in rooms]}


@router.post("/classes/join")
async def join_class(request: Request, session: Session = Depends(get_session), user: User = Depends(get_api_user)):
    body = await request.json()
    code = str(body.get("code", "")).strip().upper()
    room = session.exec(select(Classroom).where(Classroom.code == code)).first()
    if not room:
        raise HTTPException(404, "Sınıf kodu bulunamadı")
    if room.teacher_id != user.id and not session.exec(select(ClassMembership).where((ClassMembership.classroom_id == room.id) & (ClassMembership.user_id == user.id))).first():
        session.add(ClassMembership(classroom_id=room.id, user_id=user.id))
        session.commit()
    return {"ok": True, "class_id": room.id}
