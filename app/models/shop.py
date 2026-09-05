from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class ShopItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    name: str
    description: str = ""

    icon: str = "🎁"

    price: int

    type: str

    active: bool = True

    # Null = tüm öğrencilerin gördüğü genel mağaza; dolu = sınıfa özel.
    class_id: int | None = Field(default=None, foreign_key="classroom.id", index=True)


class Purchase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )

    item_id: int = Field(
        foreign_key="shopitem.id",
        index=True,
    )

    quantity: int = 1

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
