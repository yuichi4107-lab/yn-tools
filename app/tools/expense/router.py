"""経費トラッカー - ルーター"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.dependencies import require_tool_access
from app.users.models import User

router = APIRouter(prefix="/tools/expense", tags=["expense"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def expense_index(
    request: Request,
    user: User = Depends(require_tool_access("expense")),
):
    """経費トラッカー"""
    return templates.TemplateResponse(
        request, "tools/expense/index.html", {
            "user": user,
            "page": "expense",
        }
    )
