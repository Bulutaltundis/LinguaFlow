from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class XPEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    amount: int

    source: str = ""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )