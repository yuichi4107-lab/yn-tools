"""Billing routes: upgrade, webhook, portal."""

import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_login
from app.billing.stripe_service import (
    create_all_tools_checkout,
    create_billing_portal_session,
    create_tool_checkout,
    handle_checkout_completed,
    handle_invoice_paid,
    handle_subscription_deleted,
)
from app.config import settings
from app.database import get_db
from app.users.models import ToolDefinition, User

router = APIRouter(prefix="/billing", tags=["billing"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/upgrade", response_class=HTMLResponse)
async def upgrade_page(
    request: Request,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """Show upgrade/pricing page with new plan options."""
    result = await db.execute(
        select(ToolDefinition)
        .where(ToolDefinition.is_active == True)
        .order_by(ToolDefinition.display_order)
    )
    tools = result.scalars().all()
    return templates.TemplateResponse(
        request,
        "billing/upgrade.html",
        {
            "user": user,
            "tools": tools,
            "stripe_publishable_key": settings.stripe_publishable_key,
        },
    )


@router.post("/checkout")
async def create_checkout(
    request: Request,
    user: User = Depends(require_login),
):
    """Create Stripe Checkout session for all-tools plan and redirect."""
    base_url = str(request.base_url).rstrip("/")
    checkout_url = await create_all_tools_checkout(
        user=user,
        success_url=f"{base_url}/billing/success",
        cancel_url=f"{base_url}/billing/upgrade",
    )
    return RedirectResponse(url=checkout_url, status_code=303)


@router.post("/checkout/tools")
async def create_tool_checkout_route(
    request: Request,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe Checkout session for selected individual tools."""
    form = await request.form()
    tool_slugs = form.getlist("tool_slugs")
    if not tool_slugs:
        raise HTTPException(status_code=400, detail="no_tools_selected")

    base_url = str(request.base_url).rstrip("/")
    try:
        checkout_url = await create_tool_checkout(
            user=user,
            tool_slugs=tool_slugs,
            db=db,
            success_url=f"{base_url}/billing/success",
            cancel_url=f"{base_url}/billing/upgrade",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(url=checkout_url, status_code=303)


@router.get("/success", response_class=HTMLResponse)
async def checkout_success(request: Request, user: User = Depends(require_login)):
    """Post-checkout success page."""
    return templates.TemplateResponse(
        request, "billing/success.html", {"user": user}
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
