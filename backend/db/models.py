from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Parishioner(Base):
    __tablename__ = "parishioners"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    comfort_intro_shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comfort_last_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ComfortSentPassage(Base):
    __tablename__ = "comfort_sent_passages"
    __table_args__ = (Index("idx_sent_passages_user_time", "telegram_user_id", "sent_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("parishioners.telegram_user_id"), nullable=False
    )
    passage_reference: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ComfortAggregateStat(Base):
    """Anonymized /comfort usage stats. No parishioner identifier and no precise timestamp 
    column (only a coarse local time-of-day bucket), so a row can never be tied back to a 
    specific parishioner or request."""

    __tablename__ = "comfort_aggregate_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    is_crisis: Mapped[bool] = mapped_column(Boolean, nullable=False)
    emotional_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    situational_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    time_bucket: Mapped[str] = mapped_column(Text, nullable=False)
