import os
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Session, select

from app.models.apple_iap import AppleEntitlement
from app.models.user import User


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def apple_verifier():
    try:
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
        from appstoreserverlibrary.models.Environment import Environment
    except ImportError as exc:
        raise RuntimeError("Apple App Store Server Library kurulmalı: pip install app-store-server-library") from exc
    cert_path = os.getenv("APPLE_ROOT_CERT_PATH", "")
    if not cert_path:
        raise RuntimeError("APPLE_ROOT_CERT_PATH yapılandırılmamış")
    roots = []
    for item in cert_path.split(","):
        item = item.strip()
        if not item:
            continue
        path = Path(item)
        if not path.is_file():
            raise RuntimeError(f"Apple root certificate bulunamadı: {path}")
        roots.append(path.read_bytes())
    if not roots:
        raise RuntimeError("En az bir Apple root certificate gerekli")
    environment = Environment.PRODUCTION if os.getenv("APPLE_ENVIRONMENT", "sandbox").lower() == "production" else Environment.SANDBOX
    app_apple_id = int(os.getenv("APPLE_APPLE_ID")) if os.getenv("APPLE_APPLE_ID") else None
    return SignedDataVerifier(roots, True, environment, os.environ["APPLE_BUNDLE_ID"], app_apple_id)


def plan_for_product(product_id: str) -> str | None:
    if product_id == os.getenv("APPLE_MONTHLY_PRODUCT_ID"):
        return "monthly"
    if product_id == os.getenv("APPLE_YEARLY_PRODUCT_ID"):
        return "yearly"
    return None


def as_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)


def apply_transaction(user: User, transaction, session: Session):
    if user is None:
        raise ValueError("Apple transaction için kullanıcı bulunamadı")
    product_id = _field(transaction, "product_id")
    plan = plan_for_product(product_id)
    transaction_id = _field(transaction, "transaction_id")
    original_id = _field(transaction, "original_transaction_id") or transaction_id
    if not plan or not transaction_id:
        raise ValueError("Geçersiz veya tanımsız Apple product/transaction")
    expires_at = as_datetime(_field(transaction, "expires_date"))
    revocation_date = as_datetime(_field(transaction, "revocation_date"))
    status = "revoked" if revocation_date else ("active" if not expires_at or expires_at > datetime.now(timezone.utc) else "expired")
    existing = session.exec(select(AppleEntitlement).where(AppleEntitlement.transaction_id == transaction_id)).first()
    if existing and existing.user_id != user.id:
        raise ValueError("Apple transaction başka bir kullanıcıya bağlı")
    values = dict(user_id=user.id, transaction_id=transaction_id, original_transaction_id=original_id, product_id=product_id, plan=plan, environment=str(_field(transaction, "environment", "Sandbox")), status=status, expires_at=expires_at, revocation_date=revocation_date, updated_at=datetime.now(timezone.utc))
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        session.add(existing)
    else:
        session.add(AppleEntitlement(**values))
    if status == "active":
        user.subscription_plan = plan
        user.subscription_status = "active"
    else:
        active = session.exec(select(AppleEntitlement).where((AppleEntitlement.user_id == user.id) & (AppleEntitlement.status == "active") & (AppleEntitlement.transaction_id != transaction_id))).first()
        if not active:
            user.subscription_plan = None
            user.subscription_status = "free"
            user.hearts = min(5, user.hearts)
    session.add(user)
