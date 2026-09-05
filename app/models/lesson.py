from sqlmodel import Field, SQLModel


class Unit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    course_id: int = Field(foreign_key="course.id")

    title: str
    description: str = ""

    order: int = 0


class Lesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    unit_id: int = Field(foreign_key="unit.id")

    title: str
    icon: str = "📖"

    xp_reward: int = 10
    order: int = 0


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    lesson_id: int = Field(foreign_key="lesson.id")

    type: str

    prompt: str

    answer: str

    options: str = ""

    explanation: str = ""

    # Listening / future media
    audio_url: str = ""

    # Word ordering
    words: str = ""

    order: int = 0