"""SEO分析 - ルーター"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_tool_access
from app.users.models import User

router = APIRouter(prefix="/tools/seocheck", tags=["seocheck"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def seocheck_index(
    request: Request,
    user: User = Depends(require_tool_access("seocheck")),
):
    """SEO分析"""
    return templates.TemplateResponse(
        request, "tools/seocheck/index.html", {
            "user": user,
            "page": "seocheck",
        }
    )
