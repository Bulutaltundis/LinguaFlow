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
from app.core.api_auth import get_api_user
from app.core.database import get_session
from app.models.apple_iap import AppleEntitlement, AppleNotification
from app.models.billing import PaddleEvent, Subscription
from app.models.user import User
from app.services.apple_iap import apple_verifier, apply_transaction

router = APIRouter(prefix="/billing", tags=["Billing"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def billing_page(
    request: Request,
    session: Session = Depends(get_session),
):
    user = get_current_user(request, session)

    paddle_env = os.getenv("PADDLE_ENV", "sandbox").strip().lower()

    if paddle_env == "live":
        paddle_env = "production"

    return templates.TemplateResponse(
        request=request,
        name="billing/index.html",
        context={
            "user": user,
            "paddle_env": paddle_env,
            "client_token": os.getenv("PADDLE_CLIENT_TOKEN", ""),
            "monthly_price_id": os.getenv("PADDLE_MONTHLY_PRICE_ID", ""),
            "yearly_price_id": os.getenv("PADDLE_YEARLY_PRICE_ID", ""),
        },
    )


# ============================================================
# APPLE IAP - iOS TRANSACTION
# ============================================================

@router.post("/apple/transaction")
async def apple_transaction(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_api_user),
):
    """
    iOS StoreKit 2'nin gönderdiği signedTransaction'i doğrular.

    Native iOS uygulaması X-API-Key kullandığı için
    burada get_api_user kullanıyoruz.
    """

    try:
        body = await request.json()

        signed_transaction = body.get("signed_transaction")

        if not signed_transaction:
            return JSONResponse(
                {"detail": "signed_transaction gerekli"},
                status_code=400,
            )

        # Apple'ın imzaladığı transaction'ı doğrula.
        transaction = (
            apple_verifier()
            .verify_and_decode_signed_transaction(
                signed_transaction
            )
        )

        # Transaction'ın bu kullanıcıya ait olup olmadığını
        # ve Premium durumunu apply_transaction kontrol eder.
        apply_transaction(
            user,
            transaction,
            session,
        )

        session.commit()

        return {
            "ok": True,
            "plan": user.subscription_plan,
            "status": user.subscription_status,
        }

    except (ValueError, RuntimeError) as exc:
        session.rollback()

        return JSONResponse(
            {"detail": str(exc)},
            status_code=400,
        )

        except Exception as exc:
            session.rollback()

            import traceback
            traceback.print_exc()

            return JSONResponse(
                {
                    "detail": "Apple transaction doğrulanamadı",
                    "error": str(exc),
                },
                status_code=400,
            )


# ============================================================
# APPLE IAP - SERVER NOTIFICATIONS V2
# ============================================================

@router.post("/apple/notifications")
async def apple_notifications(
    request: Request,
    session: Session = Depends(get_session),
):
    """
    App Store Server Notifications V2 endpoint'i.

    Apple buraya abonelik yenileme, iptal, expiration,
    refund/revoke vb. bildirimleri gönderir.
    """

    try:
        body = await request.json()

        signed_payload = body.get("signedPayload")

        if not signed_payload:
            return JSONResponse(
                {"detail": "signedPayload gerekli"},
                status_code=400,
            )

        # Apple notification JWS doğrulaması.
        notification = (
            apple_verifier()
            .verify_and_decode_notification(
                signed_payload
            )
        )

        notification_id = getattr(
            notification,
            "notification_id",
            None,
        )

        notification_type = getattr(
            notification,
            "notification_type",
            "",
        )

        # Aynı notification daha önce işlendi mi?
        if notification_id:
            existing_notification = session.exec(
                select(AppleNotification).where(
                    AppleNotification.notification_id
                    == notification_id
                )
            ).first()

            if existing_notification:
                return {"ok": True}

            session.add(
                AppleNotification(
                    notification_id=notification_id,
                    notification_type=notification_type,
                )
            )

        data = getattr(
            notification,
            "data",
            None,
        )

        signed_transaction = (
            getattr(
                data,
                "signed_transaction_info",
                None,
            )
            if data
            else None
        )

        if signed_transaction:

            if isinstance(signed_transaction, str):
                transaction = (
                    apple_verifier()
                    .verify_and_decode_signed_transaction(
                        signed_transaction
                    )
                )
            else:
                transaction = signed_transaction

            original_id = getattr(
                transaction,
                "original_transaction_id",
                None,
            )

            if original_id:

                entitlement = session.exec(
                    select(AppleEntitlement).where(
                        AppleEntitlement.original_transaction_id
                        == original_id
                    )
                ).first()

                if entitlement:

                    user = session.get(
                        User,
                        entitlement.user_id,
                    )

                    if user:
                        apply_transaction(
                            user,
                            transaction,
                            session,
                        )

        session.commit()

        return {"ok": True}

    except Exception:
        session.rollback()

        return JSONResponse(
            {"detail": "Apple notification işlenemedi"},
            status_code=400,
        )


# ============================================================
# PADDLE WEBHOOK SIGNATURE
# ============================================================

def verify_signature(
    raw_body: bytes,
    signature: str,
    secret: str,
) -> bool:

    parts = dict(
        part.split("=", 1)
        for part in signature.split(";")
        if "=" in part
    )

    timestamp = parts.get("ts")
    received = parts.get("h1")

    if not timestamp or not received:
        return False

    try:
        # Replay attack koruması.
        if abs(time.time() - int(timestamp)) > 300:
            return False

    except ValueError:
        return False

    expected = hmac.new(
        secret.encode(),
        f"{timestamp}:".encode() + raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected,
        received,
    )


# ============================================================
# PADDLE PLAN
# ============================================================

def plan_from_data(data: dict) -> str:

    monthly = os.getenv(
        "PADDLE_MONTHLY_PRICE_ID",
        "",
    )

    yearly = os.getenv(
        "PADDLE_YEARLY_PRICE_ID",
        "",
    )

    for item in data.get("items", []):

        price = item.get("price") or {}

        price_id = (
            price.get("id")
            or item.get("price_id")
        )

        if price_id == monthly:
            return "monthly"

        if price_id == yearly:
            return "yearly"

    # Tanımsızsa varsayılan olarak monthly/yearly
    # tahmini yapmak yerine yearly döndürmemek daha güvenli.
    return "unknown"


# ============================================================
# PADDLE WEBHOOK
# ============================================================

@router.post("/webhook")
async def paddle_webhook(
    request: Request,
    session: Session = Depends(get_session),
):

    raw_body = await request.body()

    secret = os.getenv(
        "PADDLE_WEBHOOK_SECRET",
        "",
    )

    signature = request.headers.get(
        "Paddle-Signature",
        "",
    )

    # Signature zorunlu.
    if not secret or not verify_signature(
        raw_body,
        signature,
        secret,
    ):
        return JSONResponse(
            {"detail": "Invalid webhook signature"},
            status_code=401,
        )

    try:
        payload = json.loads(raw_body)

        event_id = (
            payload.get("event_id")
            or payload.get("notification_id")
        )

        event_type = payload.get(
            "event_type",
            "",
        )

        data = payload.get("data") or {}

        # Event ID yoksa işleme.
        if not event_id:
            return JSONResponse(
                {"detail": "Missing event_id"},
                status_code=400,
            )

        # Aynı webhook ikinci kez geldiyse
        # tekrar Premium işlemi yapma.
        existing_event = session.exec(
            select(PaddleEvent).where(
                PaddleEvent.event_id == event_id
            )
        ).first()

        if existing_event:
            return {"ok": True}

        session.add(
            PaddleEvent(
                event_id=event_id,
                event_type=event_type,
            )
        )

        # ----------------------------------------------------
        # USER BUL
        # ----------------------------------------------------

        custom = data.get(
            "custom_data"
        ) or {}

        user = None

        if custom.get("user_id"):

            try:
                user_id = int(
                    custom["user_id"]
                )

                user = session.get(
                    User,
                    user_id,
                )

            except (ValueError, TypeError):
                user = None

        # custom_data yoksa subscription ID üzerinden bul.
        subscription_id = (
            data.get("id")
            or data.get("subscription_id")
        )

        if not user and subscription_id:

            record = session.exec(
                select(Subscription).where(
                    Subscription.paddle_subscription_id
                    == subscription_id
                )
            ).first()

            if record:
                user = session.get(
                    User,
                    record.user_id,
                )

        # ----------------------------------------------------
        # SUPPORTED EVENTS
        # ----------------------------------------------------

        supported_events = {
            "transaction.completed",
            "subscription.created",
            "subscription.updated",
            "subscription.canceled",
        }

        if (
            user
            and event_type in supported_events
        ):

            status = data.get(
                "status",
                "active",
            )

            if event_type == "transaction.completed":
                status = "active"

            elif event_type == "subscription.canceled":
                status = "canceled"

            active = status in {
                "active",
                "trialing",
            }

            plan = (
                plan_from_data(data)
                if active
                else None
            )

            user.subscription_status = (
                status
                if active
                else "free"
            )

            user.subscription_plan = (
                plan
                if active and plan != "unknown"
                else None
            )

            user.paddle_customer_id = (
                data.get("customer_id")
                or user.paddle_customer_id
            )

            user.paddle_subscription_id = (
                subscription_id
                or user.paddle_subscription_id
            )

            # Premium bittiğinde kalpleri normal
            # maksimum değere indir.
            if not active:
                user.hearts = min(
                    5,
                    user.hearts,
                )

            session.add(user)

            # ------------------------------------------------
            # SUBSCRIPTION RECORD
            # ------------------------------------------------

            if subscription_id:

                existing_subscription = session.exec(
                    select(Subscription).where(
                        Subscription.paddle_subscription_id
                        == subscription_id
                    )
                ).first()

                if existing_subscription:

                    existing_subscription.status = status

                    if plan != "unknown":
                        existing_subscription.plan = (
                            plan
                            or existing_subscription.plan
                        )

                    existing_subscription.paddle_customer_id = (
                        user.paddle_customer_id
                    )

                    session.add(
                        existing_subscription
                    )

                else:

                    session.add(
                        Subscription(
                            user_id=user.id,
                            paddle_subscription_id=subscription_id,
                            paddle_customer_id=user.paddle_customer_id,
                            plan=(
                                plan
                                if plan != "unknown"
                                else "unknown"
                            ),
                            status=status,
                        )
                    )

        session.commit()

        return {"ok": True}

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
    ):

        session.rollback()

        return JSONResponse(
            {"detail": "Invalid webhook payload"},
            status_code=400,
        )