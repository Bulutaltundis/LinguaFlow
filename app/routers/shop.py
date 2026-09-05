from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, update

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.shop import ShopItem, Purchase
from app.models.classroom import Classroom, ClassMembership
from app.models.user import User


router = APIRouter(
    tags=["Shop"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


# ============================================================
# SHOP
# ============================================================

@router.get("/shop", response_class=HTMLResponse)
def shop_page(
    request: Request,
    class_id: int | None = None,
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

    if class_id is None:
        saved_class = request.cookies.get("active_class_id")
        class_id = int(saved_class) if saved_class and saved_class.isdigit() else None
    allowed_class = None
    allowed_room = None
    if class_id:
        room = session.get(Classroom, class_id)
        if room and (room.teacher_id == user.id or session.exec(select(ClassMembership).where((ClassMembership.classroom_id == class_id) & (ClassMembership.user_id == user.id))).first()):
            allowed_class = class_id
            allowed_room = room
    statement = select(ShopItem).where(ShopItem.active == True).order_by(ShopItem.id)
    if allowed_class:
        statement = statement.where((ShopItem.class_id == None) | (ShopItem.class_id == allowed_class))
    else:
        statement = statement.where(ShopItem.class_id == None)
    items = session.exec(statement).all()

    return templates.TemplateResponse(
        request=request,
        name="shop/index.html",
        context={
            "user": user,
            "items": items,
            "active_class_id": allowed_class,
            "active_class": allowed_room,
        },
    )


# ============================================================
# BUY ITEM
# ============================================================

@router.post("/shop/buy/{item_id}")
def buy_item(
    item_id: int,
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

    item = session.get(
        ShopItem,
        item_id,
    )

    if not item or not item.active:
        return RedirectResponse(
            "/shop?error=invalid_item",
            status_code=303,
        )

    if item.class_id:
        room = session.get(Classroom, item.class_id)
        if not room or (room.teacher_id != user.id and not session.exec(select(ClassMembership).where((ClassMembership.classroom_id == item.class_id) & (ClassMembership.user_id == user.id))).first()):
            return RedirectResponse("/shop?error=invalid_item", status_code=303)

    # Yeterli gem var mı?
    if user.gems < item.price:
        return RedirectResponse(
            "/shop?error=not_enough_gems",
            status_code=303,
        )

    # ========================================================
    # ITEM EFFECTS
    # ========================================================

    if item.type == "heart":

        user.hearts += 1

    elif item.type == "heart_pack":

        user.hearts += 5

    elif item.type == "streak_freeze":
        user.streak_freezes += 1

    elif item.type == "xp_boost":
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        current_until = user.xp_boost_until
        if current_until and current_until.tzinfo is None:
            current_until = current_until.replace(tzinfo=timezone.utc)
        user.xp_boost_until = max(current_until or now, now) + timedelta(hours=2)

    elif item.type in {
        "avatar",
        "theme",
        "cosmetic",
    }:
        if item.type == "avatar":
            user.avatar = item.icon
        elif item.type == "theme":
            user.theme = "ocean" if "okyanus" in item.name.lower() else item.name.lower().replace(" ", "-")
        else:
            user.cosmetic = item.name

    else:

        return RedirectResponse(
            "/shop?error=invalid_item",
            status_code=303,
        )

    # ========================================================
    # PAYMENT
    # ========================================================

    debit = session.exec(
        update(User)
        .where((User.id == user.id) & (User.gems >= item.price))
        .values(gems=User.gems - item.price)
    )
    if debit.rowcount != 1:
        session.rollback()
        return RedirectResponse("/shop?error=not_enough_gems", status_code=303)

    purchase = Purchase(
        user_id=user.id,
        item_id=item.id,
        quantity=1,
    )

    session.add(purchase)

    session.commit()

    return RedirectResponse(
        "/shop?success=purchased",
        status_code=303,
    )
