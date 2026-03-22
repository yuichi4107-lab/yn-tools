"""User account routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_login
from app.users.models import User

router = APIRouter(prefix="/account", tags=["account"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def account_page(request: Request, user: User = Depends(require_login)):
    """Show account/profile page with plan info."""
    return templates.TemplateResponse(
        "account/profile.html", {"request": request, "user": user}
    )
