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

app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(users_router)
app.include_router(mailer_router)
app.include_router(gems_router)
app.include_router(sales_router)
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
        return templates.TemplateResponse(
            "dashboard.html", {"request": request, "user": user, "page": "dashboard"}
        )
    return templates.TemplateResponse(
        "landing.html", {"request": request, "user": None}
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user=Depends(get_current_user)):
    """Dashboard page."""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "page": "dashboard"}
    )
