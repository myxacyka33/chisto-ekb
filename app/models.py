import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    contact_type: Mapped[str] = mapped_column(String(32))  # phone, tg, wa, vk, max, inst
    contact_value: Mapped[str] = mapped_column(String(150))
    district: Mapped[str] = mapped_column(String(100))
    service: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")  # new, in_work, completed, canceled
    review_token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: uuid.uuid4().hex)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    negative_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    media: Mapped[list["LeadMedia"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )


class LeadMedia(Base):
    __tablename__ = "lead_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(16))  # photo / video
    tg_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="media")


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    secret_token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: uuid.uuid4().hex)
    buyer_name: Mapped[str] = mapped_column(String(120))
    recipient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(150))
    contact: Mapped[str] = mapped_column(String(150))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, active, redeemed, rejected
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)