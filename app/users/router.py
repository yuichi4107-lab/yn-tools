"""User account routes."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_login
from app.billing.stripe_service import cancel_subscription
from app.database import get_db
from app.users.models import ToolDefinition, User, UserToolSubscription

router = APIRouter(prefix="/account", tags=["account"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def account_page(
    request: Request,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """Show account/profile page with plan info."""
    # 利用中ツール一覧
    subscribed_tools: list[str] = []
    if user.plan == "per_tool":
        result = await db.execute(
            select(UserToolSubscription.tool_slug).where(
                UserToolSubscription.user_id == user.id,
                UserToolSubscription.is_active == True,
            )
        )
        subscribed_tools = [row[0] for row in result.all()]

    # ツールマスタ（名前表示用）
    result = await db.execute(
        select(ToolDefinition).where(ToolDefinition.is_active == True)
        .order_by(ToolDefinition.display_order)
    )
    tools = result.scalars().all()
    tool_names = {t.slug: t.name for t in tools}

    return templates.TemplateResponse(
        request, "account/profile.html", {
            "user": user,
            "subscribed_tools": subscribed_tools,
            "tool_names": tool_names,
        }
    )


@router.get("/plan", response_class=HTMLResponse)
async def plan_page(
    request: Request,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """Show plan change page."""
    subscribed_slugs: set[str] = set()
    if user.plan == "per_tool":
        result = await db.execute(
            select(UserToolSubscription.tool_slug).where(
                UserToolSubscription.user_id == user.id,
                UserToolSubscription.is_active == True,
            )
        )
        subscribed_slugs = {row[0] for row in result.all()}

    result = await db.execute(
        select(ToolDefinition).where(ToolDefinition.is_active == True)
        .order_by(ToolDefinition.display_order)
    )
    tools = result.scalars().all()

    return templates.TemplateResponse(
        request, "account/plan.html", {
            "user": user,
            "tools": tools,
            "subscribed_slugs": subscribed_slugs,
        }
    )


@router.get("/cancel", response_class=HTMLResponse)
async def cancel_page(request: Request, user: User = Depends(require_login)):
    """Show subscription cancellation confirmation page."""
    if not user.stripe_subscription_id:
        return RedirectResponse(url="/account", status_code=303)
    return templates.TemplateResponse(
        request, "account/cancel.html", {"user": user}
    )


@router.post("/cancel")
async def cancel_action(
    request: Request,
    user: User = Depends(require_login),
    reason: str = Form(""),
):
    """Cancel subscription via Stripe."""
    if not user.stripe_subscription_id:
        return RedirectResponse(url="/account", status_code=303)

    cancel_subscription(user.stripe_subscription_id)

    return templates.TemplateResponse(
        request, "account/cancel_done.html", {"user": user, "reason": reason}
    )
