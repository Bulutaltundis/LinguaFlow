from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["Public"])


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
