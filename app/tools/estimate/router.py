"""見積書作成 - ルーター"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_tool_access
from app.users.models import User

router = APIRouter(prefix="/tools/estimate", tags=["estimate"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def estimate_index(
    request: Request,
    user: User = Depends(require_tool_access("estimate")),
):
    """見積書作成"""
    return templates.TemplateResponse(
        request, "tools/estimate/index.html", {
            "user": user,
            "page": "estimate",
        }
    )
