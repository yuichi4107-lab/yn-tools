"""Stripe API operations for subscription management."""

from datetime import datetime

import stripe
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.users.models import PaymentHistory, ToolDefinition, User, UserToolSubscription

stripe.api_key = settings.stripe_secret_key


# ---------------------------------------------------------------------------
# 料金体系: 全ツールプラン (2,000円/月) + 個別ツール (各100円/月)
# ---------------------------------------------------------------------------

async def create_all_tools_checkout(
    user: User, success_url: str, cancel_url: str
) -> str:
    """全ツールプラン（2,000円/月）のCheckout Session作成"""
    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": settings.stripe_price_all_tools, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": str(user.id), "plan_type": "all_tools"},
    }
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    else:
        params["customer_email"] = user.email
    session = stripe.checkout.Session.create(**params)
    return session.url


async def create_tool_checkout(
    user: User,
    tool_slugs: list[str],
    db: AsyncSession,
    success_url: str,
    cancel_url: str,
) -> str:
    """個別ツール購入用のCheckout Session作成"""
    result = await db.execute(
        select(ToolDefinition).where(
            ToolDefinition.slug.in_(tool_slugs),
            ToolDefinition.is_active == True,
        )
    )
    tools = result.scalars().all()
    if not tools:
        raise ValueError("No valid tools selected")

    line_items = [{"price": t.stripe_price_id, "quantity": 1} for t in tools]

    params: dict = {
        "mode": "subscription",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "user_id": str(user.id),
            "plan_type": "per_tool",
            "tool_slugs": ",".join(t.slug for t in tools),
        },
    }
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    else:
        params["customer_email"] = user.email
    session = stripe.checkout.Session.create(**params)
    return session.url


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------

async def handle_checkout_completed(session_data: dict, db: AsyncSession):
    """Handle checkout.session.completed webhook - activate subscription."""
    metadata = session_data.get("metadata", {})
    user_id = metadata.get("user_id")
    if not user_id:
        return

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        return

    plan_type = metadata.get("plan_type", "pro")
    user.stripe_customer_id = session_data.get("customer")
    user.stripe_subscription_id = session_data.get("subscription")

    if plan_type == "all_tools":
        user.plan = "all_tools"
        # 全ツールプランの場合、個別購読レコードは不要
    elif plan_type == "per_tool":
        user.plan = "per_tool"
        tool_slugs = metadata.get("tool_slugs", "").split(",")
        for slug in tool_slugs:
            if not slug:
                continue
            existing = await db.execute(
                select(UserToolSubscription).where(
                    UserToolSubscription.user_id == user.id,
                    UserToolSubscription.tool_slug == slug,
                )
            )
            sub = existing.scalar_one_or_none()
            if sub:
                sub.is_active = True
                sub.canceled_at = None
            else:
                db.add(UserToolSubscription(
                    user_id=user.id,
                    tool_slug=slug,
                    is_active=True,
                ))
    else:
        # Legacy pro plan
        user.plan = "pro"

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

    # 個別ツール購読も全て無効化
    await db.execute(
        update(UserToolSubscription)
        .where(UserToolSubscription.user_id == user.id)
        .values(is_active=False, canceled_at=datetime.utcnow())
    )

    await db.commit()


def cancel_subscription(subscription_id: str) -> None:
    """Cancel a Stripe subscription at period end."""
    stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Billing Portal session for managing subscription."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url
