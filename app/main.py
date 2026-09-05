from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from sqlmodel import Session

from app.core.database import create_db_and_tables, engine
from app.services.seed import seed_database
from app.models import XPEvent, ShopItem, Purchase
from app.routers import shop
from app.routers import profile
from app.routers import classes
from app.routers import courses

from app.routers import (
    auth,
    dashboard,
    lesson,
    admin,
    leaderboard,
)


app = FastAPI(
    title="LinguaFlow",
    description="Gamified language learning platform",
    version="0.3.0",
)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


@app.on_event("startup")
def startup():
    create_db_and_tables()

    with Session(engine) as session:
        seed_database(session)


@app.get("/")
def home():
    return RedirectResponse(
        url="/dashboard",
        status_code=303,
    )


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/learn")
def learn():
    return RedirectResponse(
        url="/dashboard",
        status_code=303,
    )


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(lesson.router)
app.include_router(admin.router)
app.include_router(leaderboard.router)
app.include_router(shop.router)
app.include_router(profile.router)
app.include_router(classes.router)
app.include_router(courses.router)
