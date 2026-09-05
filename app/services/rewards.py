from datetime import date, datetime, timezone
from sqlmodel import Session, select
from app.models.reward import Chest, UserChest, UserTask
from app.models.user import User

TASKS = [
    ("lesson", "Ders kaşifi", "Bugün 1 ders tamamla", 1, 20, "common"),
    ("questions", "Pratik zamanı", "3 doğru cevap ver", 3, 15, None),
    ("xp", "XP avcısı", "50 XP kazan", 50, 25, None),
]

def ensure_daily_tasks(user_id: int, session: Session):
    today = date.today()
    existing = {t.task_key for t in session.exec(select(UserTask).where((UserTask.user_id == user_id) & (UserTask.task_date == today))).all()}
    for key, title, description, target, gems, rarity in TASKS:
        if key not in existing:
            session.add(UserTask(user_id=user_id, task_key=key, title=title, description=description, target=target, reward_gems=gems, reward_chest_rarity=rarity, task_date=today))
    session.commit()

def update_task(user_id: int, key: str, amount: int, session: Session):
    ensure_daily_tasks(user_id, session)
    task = session.exec(select(UserTask).where((UserTask.user_id == user_id) & (UserTask.task_key == key) & (UserTask.task_date == date.today()))).first()
    if task and not task.completed:
        task.progress = min(task.target, task.progress + amount)
        if task.progress >= task.target:
            task.completed = True
        session.add(task)
        session.commit()

def claim_task(user_id: int, task_id: int, session: Session):
    task = session.get(UserTask, task_id)
    if not task or task.user_id != user_id or not task.completed or task.claimed_at:
        return False
    user = session.get(User, user_id)
    user.gems += task.reward_gems
    if task.reward_chest_rarity:
        chest = session.exec(select(Chest).where(Chest.rarity == task.reward_chest_rarity)).first()
        if chest:
            inventory = session.exec(select(UserChest).where((UserChest.user_id == user_id) & (UserChest.chest_id == chest.id))).first()
            if inventory:
                inventory.quantity += 1
            else:
                session.add(UserChest(user_id=user_id, chest_id=chest.id, quantity=1))
    task.claimed_at = datetime.now(timezone.utc)
    session.add_all([user, task])
    session.commit()
    return True
