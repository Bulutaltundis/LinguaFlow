from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserProgress(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id")
    lesson_id: int = Field(foreign_key="lesson.id")

    completed: bool = False
    score: int = 0

    completed_at: datetime | None = None