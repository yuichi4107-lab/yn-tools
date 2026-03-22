"""Billing routes: upgrade, webhook, portal."""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_login
from app.billing.stripe_service import (
    create_billing_portal_session,
    create_checkout_session,
    handle_checkout_completed,
    handle_invoice_paid,
    handle_subscription_deleted,
)
from app.config import settings
from app.database import get_db
from app.users.models import User

router = APIRouter(prefix="/billing", tags=["billing"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/upgrade", response_class=HTMLResponse)
async def upgrade_page(request: Request, user: User = Depends(require_login)):
    """Show upgrade/pricing page."""
    return templates.TemplateResponse(
        "billing/upgrade.html",
        {
            "request": request,
            "user": user,
            "stripe_publishable_key": settings.stripe_publishable_key,
        },
    )


@router.post("/checkout")
async def create_checkout(request: Request, user: User = Depends(require_login)):
    """Create Stripe Checkout session and redirect."""
    base_url = str(request.base_url).rstrip("/")
    checkout_url = await create_checkout_session(
        user=user,
        success_url=f"{base_url}/billing/success",
        cancel_url=f"{base_url}/billing/upgrade",
    )
    return RedirectResponse(url=checkout_url, status_code=303)


@router.get("/success", response_class=HTMLResponse)
async def checkout_success(request: Request, user: User = Depends(require_login)):
    """Post-checkout success page."""
    return templates.TemplateResponse(
        "billing/success.html", {"request": request, "user": user}
    )


@router.get("/portal")
async def billing_portal(request: Request, user: User = Depends(require_login)):
    """Redirect to Stripe Billing Portal for subscription management."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="no_stripe_customer")
    base_url = str(request.base_url).rstrip("/")
    portal_url = create_billing_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=f"{base_url}/account",
    )
    return RedirectResponse(url=portal_url, status_code=303)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="invalid_webhook")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(data, db)
    elif event_type == "invoice.paid":
        await handle_invoice_paid(data, db)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(data, db)

    return {"status": "ok"}
