from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserQuestionProgress(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    question_id: int = Field(
        foreign_key="question.id",
        index=True,
    )

    attempts: int = 0

    correct_count: int = 0
    incorrect_count: int = 0

    mastery: float = 0.0

    last_answer_correct: bool | None = None

    next_review_at: datetime | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )