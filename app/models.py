from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid4())


class TicketStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(180))
    role: Mapped[str] = mapped_column(String(30), default="operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(12), index=True)
    key_hash: Mapped[str] = mapped_column(String(180))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")


class Technician(Base):
    __tablename__ = "technicians"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), index=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    region: Mapped[str] = mapped_column(String(100))
    available: Mapped[bool] = mapped_column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    technician_id: Mapped[str | None] = mapped_column(ForeignKey("technicians.id"))
    source: Mapped[str] = mapped_column(String(30), default="web")
    raw_message: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(String(300))
    urgency: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default=TicketStatus.PENDING_APPROVAL)
    confidence: Mapped[float] = mapped_column(Float)
    requested_window: Mapped[str | None] = mapped_column(String(120))
    proposed_appointment: Mapped[str | None] = mapped_column(String(120))
    quote_amount: Mapped[float | None] = mapped_column(Float)
    response_draft: Mapped[str | None] = mapped_column(Text)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    customer: Mapped[Customer] = relationship(back_populates="tickets")
    technician: Mapped[Technician | None] = relationship()
    approvals: Mapped[list["Approval"]] = relationship(back_populates="ticket")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.PENDING)
    reason: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(160))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ticket: Mapped[Ticket] = relationship(back_populates="approvals")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MetricEvent(Base):
    __tablename__ = "metric_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    operation: Mapped[str] = mapped_column(String(80))
    latency_ms: Mapped[float] = mapped_column(Float)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_audit_mutation(*_):
    raise ValueError("Audit events are append-only")
