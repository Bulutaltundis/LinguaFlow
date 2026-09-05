from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    username: str = Field(
        index=True,
        unique=True,
        max_length=32,
    )

    email: str = Field(
        index=True,
        unique=True,
        max_length=255,
    )

    password_hash: str

    is_admin: bool = Field(default=False)

    # student veya teacher. Öğretmen hesabı sınıf oluşturabilir.
    role: str = Field(default="student", index=True)

    xp: int = Field(default=0)
    level: int = Field(default=1)

    gems: int = Field(default=100)
    hearts: int = Field(default=5)

    streak: int = Field(default=0)
    streak_freezes: int = Field(default=0)
    xp_boost_until: datetime | None = None
    theme: str = Field(default="default")
    cosmetic: str = Field(default="")
    avatar: str = Field(default="🧑‍💻")

    last_active: datetime | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
