from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free / pro
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @property
    def has_active_plan(self) -> bool:
        if self.plan == "pro":
            return True
        if self.trial_ends_at and self.trial_ends_at > datetime.utcnow():
            return True
        return False

    @property
    def trial_remaining_days(self) -> int | None:
        if self.plan == "pro":
            return None
        if not self.trial_ends_at:
            return 0
        delta = self.trial_ends_at - datetime.utcnow()
        return max(0, delta.days)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r}, plan={self.plan!r})>"


class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[int] = mapped_column(Integer)  # JPY
    currency: Mapped[str] = mapped_column(String(10), default="jpy")
    status: Mapped[str] = mapped_column(String(50))  # succeeded / failed / refunded
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
