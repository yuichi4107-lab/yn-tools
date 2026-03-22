"""Stripe API operations for subscription management."""

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.users.models import PaymentHistory, User

stripe.api_key = settings.stripe_secret_key


async def create_checkout_session(user: User, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session for subscription. Returns checkout URL."""
    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.stripe_price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": str(user.id)},
    }

    # Reuse existing Stripe customer if available
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    else:
        params["customer_email"] = user.email

    session = stripe.checkout.Session.create(**params)
    return session.url


async def handle_checkout_completed(session_data: dict, db: AsyncSession):
    """Handle checkout.session.completed webhook - activate subscription."""
    user_id = session_data.get("metadata", {}).get("user_id")
    if not user_id:
        return

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        return

    user.plan = "pro"
    user.stripe_customer_id = session_data.get("customer")
    user.stripe_subscription_id = session_data.get("subscription")
    await db.commit()


async def handle_invoice_paid(invoice_data: dict, db: AsyncSession):
    """Handle invoice.paid webhook - record payment."""
    customer_id = invoice_data.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    from datetime import datetime

    payment = PaymentHistory(
        user_id=user.id,
        stripe_payment_intent_id=invoice_data.get("payment_intent"),
        amount=invoice_data.get("amount_paid", 0),
        currency=invoice_data.get("currency", "jpy"),
        status="succeeded",
        paid_at=datetime.utcnow(),
    )
    db.add(payment)
    await db.commit()


async def handle_subscription_deleted(sub_data: dict, db: AsyncSession):
    """Handle customer.subscription.deleted webhook - downgrade to free."""
    customer_id = sub_data.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return

    user.plan = "free"
    user.stripe_subscription_id = None
    await db.commit()


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session for managing subscription."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url
