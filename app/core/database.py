import os
from sqlmodel import SQLModel, Session, create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./linguaflow.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    # create_all mevcut SQLite tablolarına yeni kolon eklemez.
    with engine.connect() as connection:
        user_columns = connection.execute(text("PRAGMA table_info(user)")).all()
        if not any(row[1] == "role" for row in user_columns):
            connection.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR DEFAULT 'student'"))
        for column, definition in (("streak_freezes", "INTEGER DEFAULT 0"), ("xp_boost_until", "DATETIME"), ("theme", "VARCHAR DEFAULT 'default'"), ("cosmetic", "VARCHAR DEFAULT ''"), ("avatar", "VARCHAR DEFAULT '🧑‍💻'")):
            if not any(row[1] == column for row in user_columns):
                connection.execute(text(f"ALTER TABLE user ADD COLUMN {column} {definition}"))
        shop_columns = connection.execute(text("PRAGMA table_info(shopitem)")).all()
        if not any(row[1] == "class_id" for row in shop_columns):
            connection.execute(text("ALTER TABLE shopitem ADD COLUMN class_id INTEGER"))
        connection.commit()


def get_session():
    with Session(engine) as session:
        yield session
