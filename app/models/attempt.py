from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

class QuestionAttempt(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", "question_index", name="uq_question_attempt"),)
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    lesson_id: int = Field(foreign_key="lesson.id", index=True)
    question_id: int = Field(foreign_key="question.id")
    question_index: int
    answer: str = ""
    correct: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
