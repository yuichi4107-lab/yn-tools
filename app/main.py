"""YN Tools - AI業務自動化プラットフォーム"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed GEMS/GPT library on first startup
    from app.tools.gems.service import seed_gems_items
    from app.database import async_session as _session
    async with _session() as db:
        count = await seed_gems_items(db)
        if count:
            print(f"[startup] Seeded {count} GEMS/GPT items.")

    # Seed tool definitions
    from app.users.models import ToolDefinition
    from sqlalchemy import select
    async with _session() as db:
        existing = await db.execute(select(ToolDefinition))
        if not existing.scalars().first():
            tools = [
                ToolDefinition(slug="sales", name="営業自動化", description="企業リスト・HP巡回・CRM・メール営業", monthly_price=100, display_order=1, icon_emoji="📼", stripe_product_id="prod_UDDIwP4jsIEPyk", stripe_price_id="price_1TEmrmKAVaivWwqwOO0NPLql"),
                ToolDefinition(slug="mailer", name="メール送信", description="テンプレメール一括送信・履歴管理", monthly_price=100, display_order=2, icon_emoji="✉", stripe_product_id="prod_UDDISonnzcKLmO", stripe_price_id="price_1TEms7KAVaivWwqwabRK9pJb"),
                ToolDefinition(slug="gems", name="GEMS/GPTライブラリ", description="AI業務改善プロンプト200本", monthly_price=100, display_order=3, icon_emoji="✨", stripe_product_id="prod_UDDKTlnnnfoPeR", stripe_price_id="price_1TEmtNKAVaivWwqwmeG7NnWK"),
                ToolDefinition(slug="docai", name="AI文書処理", description="PDF・テキストをAIで要約・翻訳・Q&A・情報抽出", monthly_price=100, display_order=4, icon_emoji="📄"),
                ToolDefinition(slug="contentgen", name="AIコンテンツ生成", description="SNS投稿・ブログ記事・広告コピー・メールをAI自動作成", monthly_price=100, display_order=5, icon_emoji="✍"),
                ToolDefinition(slug="webresearch", name="AI Webリサーチャー", description="URLを入力→AIがページ分析・要約・競合比較", monthly_price=100, display_order=6, icon_emoji="🔍"),
                ToolDefinition(slug="imagegen", name="AI画像生成", description="プロンプトからSNS画像・バナー・商品画像を一括生成", monthly_price=100, display_order=7, icon_emoji="🎨"),
                ToolDefinition(slug="chatbot", name="AIチャットボットビルダー", description="自社サイトに埋め込めるAIチャットボットを作成・管理", monthly_price=100, display_order=8, icon_emoji="🤖"),
            ]
            db.add_all(tools)
            await db.commit()
            print("[startup] Seeded 3 tool definitions.")

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Session middleware (signed cookie for auth)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
from app.auth.router import router as auth_router
from app.billing.router import router as billing_router
from app.users.router import router as users_router
from app.tools.mailer.router import router as mailer_router
from app.tools.gems.router import router as gems_router
from app.tools.sales.router import router as sales_router
from app.community.router import router as community_router
from app.tools.docai.router import router as docai_router
from app.tools.contentgen.router import router as contentgen_router
from app.tools.webresearch.router import router as webresearch_router
from app.tools.imagegen.router import router as imagegen_router
from app.tools.chatbot.router import router as chatbot_router

app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(users_router)
app.include_router(mailer_router)
app.include_router(gems_router)
app.include_router(sales_router)
app.include_router(docai_router)
app.include_router(contentgen_router)
app.include_router(webresearch_router)
app.include_router(imagegen_router)
app.include_router(chatbot_router)
app.include_router(community_router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/health")
async def health_check():
    """Health check for Render monitoring."""
    from sqlalchemy import text
    from app.database import async_session
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "db": "connected"})
    except Exception as e:
        return JSONResponse({"status": "error", "db": str(e)}, status_code=503)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request, user=Depends(get_current_user)):
    """Landing page (top) or redirect to dashboard if logged in."""
    if user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "landing.html", {"user": None}
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    """Dashboard page."""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=303)

    # 個別ツール購読中のslug一覧を取得
    # is_active=True OR 削除予約中（canceled_at が未来）のツールも含む
    subscribed_tools: set[str] = set()
    if user.plan == "per_tool":
        from datetime import datetime as _dt
        from sqlalchemy import or_, and_, select
        from app.database import get_db as _get_db
        from app.database import async_session
        from app.users.models import UserToolSubscription
        async with async_session() as db:
            result = await db.execute(
                select(UserToolSubscription.tool_slug).where(
                    UserToolSubscription.user_id == user.id,
                    or_(
                        UserToolSubscription.is_active == True,
                        and_(
                            UserToolSubscription.canceled_at != None,
                            UserToolSubscription.canceled_at > _dt.utcnow(),
                        ),
                    ),
                )
            )
            subscribed_tools = {row[0] for row in result.all()}

    # Stripeサブスクリプション情報（有効期間・自動更新）
    subscription_info = None
    if user.stripe_subscription_id:
        from app.users.router import _get_subscription_info
        subscription_info = _get_subscription_info(user.stripe_subscription_id)

    # Free期間中の有料開始日（trial_ends_atの翌日）
    paid_start_date = None
    if user.is_in_trial and user.trial_ends_at:
        from datetime import timedelta as _td
        paid_start = (user.trial_ends_at + _td(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        paid_start_date = paid_start.strftime("%Y年%m月%d日")

    return templates.TemplateResponse(
        request, "dashboard.html", {
            "user": user,
            "page": "dashboard",
            "subscribed_tools": subscribed_tools,
            "subscription_info": subscription_info,
            "paid_start_date": paid_start_date,
        }
    )
