import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.billing import PaddleEvent, Subscription
from app.models.user import User
from app.models.apple_iap import AppleNotification, AppleEntitlement
from app.services.apple_iap import apple_verifier, apply_transaction

router = APIRouter(prefix="/billing", tags=["Billing"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def billing_page(request: Request, session: Session = Depends(get_session)):
    user = get_current_user(request, session)
    paddle_env = os.getenv("PADDLE_ENV", "sandbox").strip().lower()
    if paddle_env == "live":
        paddle_env = "production"
    return templates.TemplateResponse(request=request, name="billing/index.html", context={
        "user": user,
        "paddle_env": paddle_env,
        "client_token": os.getenv("PADDLE_CLIENT_TOKEN", ""),
        "monthly_price_id": os.getenv("PADDLE_MONTHLY_PRICE_ID", ""),
        "yearly_price_id": os.getenv("PADDLE_YEARLY_PRICE_ID", ""),
    })


@router.post("/apple/transaction")
async def apple_transaction(request: Request, session: Session = Depends(get_session)):
    """iOS, StoreKit'ten aldığı signedTransaction'i bu endpoint'e yollar."""
    user = get_current_user(request, session)
    if not user:
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    try:
        body = await request.json()
        signed_transaction = body.get("signed_transaction")
        if not signed_transaction:
            return JSONResponse({"detail": "signed_transaction gerekli"}, status_code=400)
        transaction = apple_verifier().verify_and_decode_signed_transaction(signed_transaction)
        apply_transaction(user, transaction, session)
        session.commit()
        return {"ok": True, "plan": user.subscription_plan, "status": user.subscription_status}
    except (ValueError, RuntimeError) as exc:
        session.rollback()
        return JSONResponse({"detail": str(exc)}, status_code=400)
    except Exception:
        session.rollback()
        return JSONResponse({"detail": "Apple transaction doğrulanamadı"}, status_code=400)


@router.post("/apple/notifications")
async def apple_notifications(request: Request, session: Session = Depends(get_session)):
    """App Store Server Notifications V2 endpoint'i."""
    try:
        body = await request.json()
        signed_payload = body.get("signedPayload")
        if not signed_payload:
            return JSONResponse({"detail": "signedPayload gerekli"}, status_code=400)
        notification = apple_verifier().verify_and_decode_notification(signed_payload)
        notification_id = getattr(notification, "notification_id", None)
        notification_type = getattr(notification, "notification_type", "")
        if notification_id and session.exec(select(AppleNotification).where(AppleNotification.notification_id == notification_id)).first():
            return {"ok": True}
        if notification_id:
            session.add(AppleNotification(notification_id=notification_id, notification_type=notification_type))
        data = getattr(notification, "data", None)
        signed_transaction = getattr(data, "signed_transaction_info", None) if data else None
        if signed_transaction:
            # Library sürümüne göre bu alan zaten decoded payload veya JWS olabilir.
            transaction = (apple_verifier().verify_and_decode_signed_transaction(signed_transaction)
                           if isinstance(signed_transaction, str) else signed_transaction)
            original_id = getattr(transaction, "original_transaction_id", None)
            entitlement = session.exec(select(AppleEntitlement).where(AppleEntitlement.original_transaction_id == original_id)).first()
            if entitlement:
                user = session.get(User, entitlement.user_id)
                apply_transaction(user, transaction, session)
        session.commit()
        return {"ok": True}
    except Exception:
        session.rollback()
        return JSONResponse({"detail": "Apple notification işlenemedi"}, status_code=400)


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    parts = dict(part.split("=", 1) for part in signature.split(";") if "=" in part)
    timestamp, received = parts.get("ts"), parts.get("h1")
    if not timestamp or not received:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}:".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


def plan_from_data(data: dict) -> str:
    monthly = os.getenv("PADDLE_MONTHLY_PRICE_ID", "")
    for item in data.get("items", []):
        price_id = (item.get("price") or {}).get("id") or item.get("price_id")
        if price_id == monthly:
            return "monthly"
    return "yearly"


@router.post("/webhook")
async def paddle_webhook(request: Request, session: Session = Depends(get_session)):
    raw_body = await request.body()
    secret = os.getenv("PADDLE_WEBHOOK_SECRET", "")
    signature = request.headers.get("Paddle-Signature", "")
    if not secret or not verify_signature(raw_body, signature, secret):
        return JSONResponse({"detail": "Invalid webhook signature"}, status_code=401)
    try:
        payload = json.loads(raw_body)
        event_id = payload.get("event_id") or payload.get("notification_id")
        event_type = payload.get("event_type", "")
        data = payload.get("data") or {}
        if not event_id or session.exec(select(PaddleEvent).where(PaddleEvent.event_id == event_id)).first():
            return {"ok": True}
        session.add(PaddleEvent(event_id=event_id, event_type=event_type))
        custom = data.get("custom_data") or {}
        user = session.get(User, int(custom["user_id"])) if custom.get("user_id") else None
        subscription_id = data.get("id") or data.get("subscription_id")
        if not user and subscription_id:
            record = session.exec(select(Subscription).where(Subscription.paddle_subscription_id == subscription_id)).first()
            user = session.get(User, record.user_id) if record else None
        if user and event_type in {"transaction.completed", "subscription.created", "subscription.updated", "subscription.canceled"}:
            status = data.get("status", "active")
            if event_type == "transaction.completed":
                status = "active"
            if event_type == "subscription.canceled":
                status = "canceled"
            active = status in {"active", "trialing"}
            user.subscription_status = status if active else "free"
            user.subscription_plan = plan_from_data(data) if active else None
            user.paddle_customer_id = data.get("customer_id") or user.paddle_customer_id
            user.paddle_subscription_id = subscription_id or user.paddle_subscription_id
            if not active:
                user.hearts = min(5, user.hearts)
            session.add(user)
            if subscription_id:
                existing = session.exec(select(Subscription).where(Subscription.paddle_subscription_id == subscription_id)).first()
                if existing:
                    existing.status, existing.plan = status, user.subscription_plan or existing.plan
                    session.add(existing)
                else:
                    session.add(Subscription(user_id=user.id, paddle_subscription_id=subscription_id, paddle_customer_id=user.paddle_customer_id, plan=user.subscription_plan or "yearly", status=status))
        session.commit()
        return {"ok": True}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        session.rollback()
        return JSONResponse({"detail": "Invalid webhook payload"}, status_code=400)
