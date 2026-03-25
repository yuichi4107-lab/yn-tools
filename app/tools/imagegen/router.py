"""AI画像一括生成ツール - ルーター"""

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_tool_access
from app.database import get_db
from app.users.models import User

from .models import ImageGenHistory
from . import service

router = APIRouter(prefix="/tools/imagegen", tags=["imagegen"])
templates = Jinja2Templates(directory="app/templates")


# ---------- UI ----------

@router.get("/", response_class=HTMLResponse)
async def imagegen_index(
    request: Request,
    user: User = Depends(require_tool_access("imagegen")),
    db: AsyncSession = Depends(get_db),
):
    """AI画像生成 ダッシュボード"""
    stats = await db.execute(
        select(
            func.count(ImageGenHistory.id),
            func.coalesce(func.sum(ImageGenHistory.count), 0),
        ).where(ImageGenHistory.user_id == user.id)
    )
    row = stats.one()
    total_uses = row[0]
    total_images = row[1]

    recent = await db.execute(
        select(ImageGenHistory)
        .where(ImageGenHistory.user_id == user.id)
        .order_by(ImageGenHistory.created_at.desc())
        .limit(10)
    )
    history = recent.scalars().all()

    return templates.TemplateResponse(
        request, "tools/imagegen/index.html", {
            "user": user,
            "page": "imagegen",
            "total_uses": total_uses,
            "total_images": total_images,
            "history": history,
            "style_presets": service.get_style_presets(),
        }
    )


# ---------- 画像生成 API ----------

@router.post("/api/generate")
async def api_generate(
    user: User = Depends(require_tool_access("imagegen")),
    db: AsyncSession = Depends(get_db),
    prompt: str = Form(default=""),
    style: str = Form(default="none"),
    size: str = Form(default="1024x1024"),
    count: int = Form(default=1),
):
    """画像生成"""
    if not prompt.strip():
        return {"error": "プロンプトを入力してください。"}

    # サイズバリデーション
    valid_sizes = ["1024x1024", "1536x1024", "1024x1536"]
    if size not in valid_sizes:
        size = "1024x1024"

    try:
        urls = await service.generate_images(
            prompt=prompt.strip(),
            style=style,
            size=size,
            count=min(count, 4),
        )
    except Exception as e:
        return {"error": f"画像生成に失敗しました: {e}"}

    # 履歴保存
    history = ImageGenHistory(
        user_id=user.id,
        prompt=prompt[:2000],
        style=style,
        size=size,
        count=len(urls),
        image_urls=json.dumps(urls),
    )
    db.add(history)
    await db.commit()

    return {"urls": urls, "count": len(urls)}


# ---------- 履歴の画像URL取得 ----------

@router.get("/api/history/{history_id}")
async def api_history_detail(
    history_id: int,
    user: User = Depends(require_tool_access("imagegen")),
    db: AsyncSession = Depends(get_db),
):
    """履歴の詳細取得"""
    result = await db.execute(
        select(ImageGenHistory).where(
            ImageGenHistory.id == history_id,
            ImageGenHistory.user_id == user.id,
        )
    )
    h = result.scalar_one_or_none()
    if not h:
        return {"error": "見つかりません。"}

    return {
        "prompt": h.prompt,
        "style": h.style,
        "size": h.size,
        "count": h.count,
        "urls": json.loads(h.image_urls) if h.image_urls else [],
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }
