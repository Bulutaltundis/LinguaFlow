from sqlmodel import Field, SQLModel


class Course(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    language: str
    description: str = ""
    icon: str = "🌍"