from app.models.user import User

ACTIVE_STATUSES = {"active", "trialing"}

def has_unlimited_hearts(user: User) -> bool:
    return bool(user.subscription_plan in {"monthly", "yearly"} and user.subscription_status in ACTIVE_STATUSES)
