"""Auth routes: Google OAuth login/logout."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google_oauth import oauth
from app.config import settings
from app.database import get_db
from app.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page with Google sign-in button."""
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.get("/google")
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        return RedirectResponse(url="/auth/login?error=auth_failed", status_code=303)

    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name", email)
    avatar_url = userinfo.get("picture")

    # Find or create user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user:
        # Update profile info from Google
        user.name = name
        user.avatar_url = avatar_url
    else:
        # New user - create with trial period
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
            plan="free",
            trial_ends_at=datetime.utcnow() + timedelta(days=settings.trial_days),
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # Set session
    request.session["user_id"] = user.id

    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to top page."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
