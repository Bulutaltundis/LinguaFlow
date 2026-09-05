from datetime import datetime, timezone
from sqlmodel import Field, SQLModel

class Subscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    paddle_customer_id: str | None = Field(default=None, index=True)
    paddle_subscription_id: str = Field(index=True, unique=True)
    plan: str
    status: str = "active"
    next_billed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaddleEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(index=True, unique=True)
    event_type: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
