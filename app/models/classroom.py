from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Classroom(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    code: str = Field(index=True, unique=True, max_length=7)
    teacher_id: int = Field(foreign_key="user.id", index=True)
    course_id: int | None = Field(default=None, foreign_key="course.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClassMembership(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    classroom_id: int = Field(foreign_key="classroom.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Assignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    classroom_id: int = Field(foreign_key="classroom.id", index=True)
    title: str
    lesson_count: int = 2
    due_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClassShopItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    classroom_id: int = Field(foreign_key="classroom.id", index=True)
    name: str
    description: str = ""
    icon: str = "🎁"
    price: int
    type: str
    active: bool = True
