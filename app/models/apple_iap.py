from datetime import datetime, timezone
from sqlmodel import Field, SQLModel

class AppleEntitlement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    transaction_id: str = Field(index=True, unique=True)
    original_transaction_id: str = Field(index=True)
    product_id: str
    plan: str
    environment: str = "Sandbox"
    status: str = "active"
    expires_at: datetime | None = None
    revocation_date: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AppleNotification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    notification_id: str = Field(index=True, unique=True)
    notification_type: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
