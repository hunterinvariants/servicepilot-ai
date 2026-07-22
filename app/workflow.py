from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import randint

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters import CalendarAdapter, CRMAdapter, EmailAdapter, WebhookAdapter
from app.ai import get_provider
from app.config import get_settings
from app.knowledge import retrieve
from app.models import Approval, ApprovalStatus, AuditEvent, Customer, MetricEvent, Technician, Ticket, TicketStatus
from app.schemas import ServiceRequest


def audit(db: Session, organization_id: str, event_type: str, detail: dict,
          ticket_id: str | None = None, actor: str = "system"):
    db.add(AuditEvent(organization_id=organization_id, ticket_id=ticket_id, actor=actor,
                      event_type=event_type, detail=detail))


def suggest_technician(db: Session, organization_id: str, category: str) -> Technician | None:
    candidates = db.scalars(select(Technician).where(Technician.organization_id == organization_id,
                                                     Technician.available.is_(True))).all()
    return next((tech for tech in candidates if category in tech.skills), candidates[0] if candidates else None)


def create_intake(db: Session, request: ServiceRequest, organization_id: str) -> Ticket:
    provider = get_provider(get_settings())
    result, metrics = provider.classify(request)
    customer = db.scalar(select(Customer).where(Customer.organization_id == organization_id,
                                                Customer.email == request.email))
    if customer is None:
        customer = Customer(organization_id=organization_id, name=request.name, email=request.email,
                            phone=request.phone, address=request.address)
        db.add(customer)
        db.flush()
    tech = suggest_technician(db, organization_id, result.category)
    count = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.organization_id == organization_id)) or 0
    reference = f"SP-{datetime.now(timezone.utc):%y%m%d}-{count + randint(10, 99):04d}"
    proposed = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%a %d %b, 09:00-11:00")
    risky = bool(result.risk_flags) or result.urgency in {"high", "emergency"}
    ticket = Ticket(organization_id=organization_id, reference=reference, customer_id=customer.id,
        technician_id=tech.id if tech else None, source=request.source, raw_message=request.message,
        category=result.category, summary=result.summary, urgency=result.urgency, confidence=result.confidence,
        requested_window=result.requested_window, proposed_appointment=proposed,
        quote_amount=result.quote_amount, response_draft=result.response_draft, risk_flags=result.risk_flags,
        status=TicketStatus.ESCALATED if risky else TicketStatus.PENDING_APPROVAL)
    db.add(ticket)
    db.flush()
    reason = "Risk or uncertainty requires review" if risky else "Approve quote, technician, appointment, and response"
    db.add(Approval(organization_id=organization_id, ticket_id=ticket.id,
                    action="confirm_service_plan", reason=reason))
    db.add(MetricEvent(organization_id=organization_id, provider=provider.name, operation="classify",
                       latency_ms=metrics["latency_ms"], input_tokens=metrics["input_tokens"],
                       output_tokens=metrics["output_tokens"]))
    audit(db, organization_id, "ai_intake_completed", {"provider": provider.name,
          "classification": result.model_dump(), "technician": tech.name if tech else None,
          "knowledge": retrieve(request.message)}, ticket.id, "ai-agent")
    db.commit()
    db.refresh(ticket)
    return ticket


def decide_approval(db: Session, approval: Approval, approve: bool, decided_by: str, note: str = "") -> Ticket:
    if approval.status != ApprovalStatus.PENDING:
        raise ValueError("Approval was already decided")
    approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    ticket = approval.ticket
    ticket.status = TicketStatus.SCHEDULED if approve else TicketStatus.ESCALATED
    audit(db, ticket.organization_id, "service_plan_approved" if approve else "service_plan_rejected",
          {"action": approval.action, "note": note}, ticket.id, decided_by)
    if approve:
        settings = get_settings()
        results = [CalendarAdapter().reserve(ticket), CRMAdapter().sync(ticket), EmailAdapter(settings).draft(ticket)]
        for result in results:
            audit(db, ticket.organization_id, "adapter_action_completed", result.__dict__, ticket.id, "approval-executor")
    db.commit()
    return ticket


def generate_quote(ticket: Ticket, output_dir: str = "quotes") -> Path:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ticket.reference}.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"ServicePilot quote {ticket.reference}")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(55, 780, "ServicePilot AI")
    pdf.setFont("Helvetica", 11)
    lines = [f"Quote: {ticket.reference}", f"Customer: {ticket.customer.name}",
             f"Service: {ticket.category.title()}", f"Summary: {ticket.summary}",
             f"Proposed appointment: {ticket.proposed_appointment}",
             f"Estimated total: CHF {ticket.quote_amount or 0:.2f}",
             "This quote is subject to human approval and on-site diagnosis."]
    y = 730
    for line in lines:
        pdf.drawString(55, y, line[:100])
        y -= 28
    pdf.save()
    return path


def dispatch_webhook(ticket_id: str):
    from app.database import SessionLocal
    settings = get_settings()
    if not settings.webhook_url:
        return
    with SessionLocal() as db:
        ticket = db.get(Ticket, ticket_id)
        if ticket:
            WebhookAdapter(settings.webhook_url, settings.webhook_signing_secret).send(ticket)
