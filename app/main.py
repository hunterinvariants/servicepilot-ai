from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base, engine, get_db
from app.models import Approval, ApprovalStatus, AuditEvent, Customer, MetricEvent, Ticket
from app.schemas import Decision, ServiceRequest
from app.worker import enqueue_webhook
from app.workflow import create_intake, decide_approval, generate_quote


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ServicePilot AI", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def load_ticket(db: Session, ticket_id: str) -> Ticket:
    ticket = db.scalar(select(Ticket).options(selectinload(Ticket.customer), selectinload(Ticket.technician),
                       selectinload(Ticket.approvals)).where(Ticket.id == ticket_id))
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return ticket


@app.get("/health")
def health():
    return {"status": "ok", "service": "servicepilot-ai"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    tickets = db.scalars(select(Ticket).options(selectinload(Ticket.customer), selectinload(Ticket.technician))
                         .order_by(Ticket.created_at.desc()).limit(20)).all()
    pending = db.scalar(select(func.count()).select_from(Approval).where(Approval.status == ApprovalStatus.PENDING)) or 0
    customers = db.scalar(select(func.count()).select_from(Customer)) or 0
    avg_latency = db.scalar(select(func.avg(MetricEvent.latency_ms))) or 0
    return templates.TemplateResponse(request, "dashboard.html", {"tickets": tickets, "pending": pending,
                                      "customers": customers, "avg_latency": avg_latency})


@app.get("/intake", response_class=HTMLResponse)
def intake_form(request: Request):
    return templates.TemplateResponse(request, "intake.html", {})


@app.post("/intake")
def intake_submit(name: str = Form(), email: str = Form(), phone: str = Form(""), address: str = Form(),
                  message: str = Form(), requested_window: str = Form(""), db: Session = Depends(get_db)):
    ticket = create_intake(db, ServiceRequest(name=name, email=email, phone=phone or None, address=address,
                           message=message, requested_window=requested_window or None))
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=303)


@app.post("/api/v1/intakes", status_code=201)
def api_intake(payload: ServiceRequest, db: Session = Depends(get_db)):
    ticket = create_intake(db, payload)
    return {"id": ticket.id, "reference": ticket.reference, "status": ticket.status,
            "approval_required": True, "risk_flags": ticket.risk_flags}


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    ticket = load_ticket(db, ticket_id)
    events = db.scalars(select(AuditEvent).where(AuditEvent.ticket_id == ticket_id).order_by(AuditEvent.created_at.desc())).all()
    return templates.TemplateResponse(request, "ticket.html", {"ticket": ticket, "events": events})


@app.post("/approvals/{approval_id}/{decision}")
def approval_decision(approval_id: str, decision: str, decided_by: str = Form(), note: str = Form(""),
                      db: Session = Depends(get_db)):
    approval = db.scalar(select(Approval).options(selectinload(Approval.ticket)).where(Approval.id == approval_id))
    if not approval or decision not in {"approve", "reject"}:
        raise HTTPException(404, "Approval not found")
    try:
        ticket = decide_approval(db, approval, decision == "approve", decided_by, note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    enqueue_webhook(ticket.id)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=303)


@app.post("/api/v1/approvals/{approval_id}/{decision}")
def api_approval(approval_id: str, decision: str, payload: Decision, db: Session = Depends(get_db)):
    approval = db.scalar(select(Approval).options(selectinload(Approval.ticket)).where(Approval.id == approval_id))
    if not approval or decision not in {"approve", "reject"}:
        raise HTTPException(404, "Approval not found")
    ticket = decide_approval(db, approval, decision == "approve", payload.decided_by, payload.note)
    enqueue_webhook(ticket.id)
    return {"ticket_id": ticket.id, "status": ticket.status}


@app.get("/tickets/{ticket_id}/quote.pdf")
def quote(ticket_id: str, db: Session = Depends(get_db)):
    ticket = load_ticket(db, ticket_id)
    path = generate_quote(ticket)
    return FileResponse(path, media_type="application/pdf", filename=path.name)

