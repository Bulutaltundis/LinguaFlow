from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class APIKey(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_prefix: str = Field(index=True)
    key_hash: str = Field(index=True, unique=True)
    name: str = "mobile"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
