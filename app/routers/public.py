import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.database import get_session


templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["Public"])


def landing_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    return templates.TemplateResponse(request=request, name="public/home.html", context={
        "user": user,
        "monthly_price_id": os.getenv("PADDLE_MONTHLY_PRICE_ID", ""),
        "yearly_price_id": os.getenv("PADDLE_YEARLY_PRICE_ID", ""),
    })


@router.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="public/terms.html", context={})


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="public/privacy.html", context={})


@router.get("/refund", response_class=HTMLResponse)
def refund_page(request: Request):
    return templates.TemplateResponse(request=request, name="public/refund.html", context={})


@router.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="public/contact.html", context={})
