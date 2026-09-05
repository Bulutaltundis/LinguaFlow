import secrets
from datetime import date
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, update
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.reward import Chest, UserChest, UserTask
from app.models.user import User
from app.services.rewards import ensure_daily_tasks, claim_task

router = APIRouter(prefix="/rewards", tags=["Rewards"])
templates = Jinja2Templates(directory="app/templates")

@router.get("", response_class=HTMLResponse)
def rewards_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    ensure_daily_tasks(user.id, session)
    tasks = session.exec(select(UserTask).where((UserTask.user_id == user.id) & (UserTask.task_date == date.today()))).all()
    inventory = []
    for owned in session.exec(select(UserChest).where((UserChest.user_id == user.id) & (UserChest.quantity > 0))).all():
        inventory.append({"owned": owned, "chest": session.get(Chest, owned.chest_id)})
    return templates.TemplateResponse(request=request, name="rewards/index.html", context={"user": user, "tasks": tasks, "inventory": inventory})

@router.post("/tasks/{task_id}/claim")
def claim(task_id: int, request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    claim_task(user.id, task_id, session)
    return RedirectResponse("/rewards?success=claimed", status_code=303)

@router.post("/chests/{chest_id}/open")
def open_chest(chest_id: int, request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    chest = session.get(Chest, chest_id)
    if not user or not chest:
        return RedirectResponse("/rewards", status_code=303)
    result = session.exec(update(UserChest).where((UserChest.user_id == user.id) & (UserChest.chest_id == chest_id) & (UserChest.quantity > 0)).values(quantity=UserChest.quantity - 1))
    if result.rowcount != 1:
        return RedirectResponse("/rewards?error=no_chest", status_code=303)
    gems = secrets.randbelow(chest.max_gems - chest.min_gems + 1) + chest.min_gems
    session.exec(update(User).where(User.id == user.id).values(gems=User.gems + gems))
    session.commit()
    return RedirectResponse(f"/rewards?opened={gems}&rarity={chest.rarity}", status_code=303)
