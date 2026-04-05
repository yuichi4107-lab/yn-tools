"""名刺リーダー - ルーター"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_tool_access
from app.users.models import User

router = APIRouter(prefix="/tools/cardreader", tags=["cardreader"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def cardreader_index(
    request: Request,
    user: User = Depends(require_tool_access("cardreader")),
):
    """名刺リーダー"""
    return templates.TemplateResponse(
        request, "tools/cardreader/index.html", {
            "user": user,
            "page": "cardreader",
        }
    )
