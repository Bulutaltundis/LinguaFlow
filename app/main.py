import os
from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from sqlmodel import Session

from app.core.database import create_db_and_tables, engine
from app.services.seed import seed_database
from app.models import XPEvent, ShopItem, Purchase
from app.routers import shop
from app.routers import profile
from app.routers import classes
from app.routers import courses
from app.routers import rewards
from app.routers import billing
from app.routers import public
from dotenv import load_dotenv

load_dotenv()

from app.routers import (
    auth,
    dashboard,
    lesson,
    admin,
    leaderboard,
)
from app.core.middleware import SecurityMiddleware
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User


production = os.getenv("APP_ENV", "development").lower() == "production"
app = FastAPI(
    title="LinguaFlow",
    description="Gamified language learning platform",
    version="0.3.0",
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)
app.add_middleware(SecurityMiddleware)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

@app.get("/media/audio/{filename}")
def audio_file(filename: str, request: Request, session=Depends(get_session)):
    if not get_current_user(request, session):
        return RedirectResponse("/auth/login", status_code=303)
    safe_name = Path(filename).name
    path = Path("app/uploads/audio") / safe_name
    if safe_name != filename or not path.is_file():
        return RedirectResponse("/", status_code=404)
    return FileResponse(path)


@app.on_event("startup")
def startup():
    create_db_and_tables()

    with Session(engine) as session:
        seed_database(session)


@app.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    if get_current_user(request, session):
        return RedirectResponse(
            url="/dashboard",
            status_code=303,
        )
    return RedirectResponse(
        url="/billing",
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
app.include_router(rewards.router)
app.include_router(billing.router)
app.include_router(public.router)
