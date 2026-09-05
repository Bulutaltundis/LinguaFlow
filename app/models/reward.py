from datetime import date, datetime, timezone
from sqlmodel import Field, SQLModel

class Chest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    rarity: str = Field(index=True)
    icon: str = "📦"
    min_gems: int = 10
    max_gems: int = 30

class UserChest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    chest_id: int = Field(foreign_key="chest.id", index=True)
    quantity: int = 0

class UserTask(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    task_key: str = Field(index=True)
    title: str
    description: str = ""
    target: int
    progress: int = 0
    reward_gems: int = 0
    reward_chest_rarity: str | None = None
    task_date: date = Field(default_factory=date.today, index=True)
    completed: bool = False
    claimed_at: datetime | None = None
