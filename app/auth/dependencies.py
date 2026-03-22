"""Auth dependencies for FastAPI route injection."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.users.models import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Get current logged-in user from session cookie. Returns None if not logged in."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def require_login(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require authenticated user. Raises 401 if not logged in."""
    if not user:
        raise HTTPException(status_code=401, detail="login_required")
    return user


async def require_active_plan(
    user: User = Depends(require_login),
) -> User:
    """Require user with active plan (pro or within trial). Raises 402 if expired."""
    if user.has_active_plan:
        return user
    raise HTTPException(status_code=402, detail="plan_expired")


async def require_admin(
    user: User = Depends(require_login),
) -> User:
    """Require admin user. Raises 403 if not admin."""
    if user.is_admin:
        return user
    raise HTTPException(status_code=403, detail="admin_required")
