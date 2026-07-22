from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from app.ai import get_provider
from app.auth import current_principal, hash_secret, rate_limiter, require_principal, verify_secret
from app.config import get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.evaluation import run_evaluation
from app.models import Approval, ApprovalStatus, AuditEvent, Customer, MetricEvent, Organization, Ticket, User
from app.schemas import Decision, ServiceRequest
from app.worker import enqueue_webhook
from app.workflow import create_intake, decide_approval, generate_quote

settings = get_settings()


def bootstrap():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "servicepilot-demo"))
        if not org:
            org = Organization(name="ServicePilot Demo", slug="servicepilot-demo")
            db.add(org)
            db.flush()
        user = db.scalar(select(User).where(User.email == settings.admin_email))
        if not user:
            db.add(User(organization_id=org.id, email=settings.admin_email,
                        password_hash=hash_secret(settings.admin_password), role="admin"))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="ServicePilot AI", version="0.2.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax",
                   https_only=settings.app_env == "production")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:"
    return response


def demo_org_id(db: Session) -> str:
    org = db.scalar(select(Organization).where(Organization.slug == "servicepilot-demo"))
    if not org:
        raise HTTPException(503, "Organization unavailable")
    return org.id


def load_ticket(db: Session, ticket_id: str, organization_id: str) -> Ticket:
    ticket = db.scalar(select(Ticket).options(selectinload(Ticket.customer), selectinload(Ticket.technician),
                       selectinload(Ticket.approvals)).where(Ticket.id == ticket_id,
                                                           Ticket.organization_id == organization_id))
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return ticket


@app.get("/health")
def health():
    return {"status": "ok", "service": "servicepilot-ai", "version": app.version}


@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse(request, "home.html", {})


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(request: Request, email: str = Form(), password: str = Form(), db: Session = Depends(get_db)):
    rate_limiter.check(f"login:{request.client.host if request.client else 'unknown'}", 10, 300)
    user = db.scalar(select(User).where(User.email == email, User.active.is_(True)))
    if not user or not verify_secret(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"}, status_code=401)
    request.session["user_id"] = user.id
    return RedirectResponse("/ops", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/ops", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    principal = current_principal(request, db)
    if not principal:
        return RedirectResponse("/login", status_code=303)
    scope = Ticket.organization_id == principal.organization_id
    tickets = db.scalars(select(Ticket).options(selectinload(Ticket.customer), selectinload(Ticket.technician))
                         .where(scope).order_by(Ticket.created_at.desc()).limit(20)).all()
    pending = db.scalar(select(func.count()).select_from(Approval).where(
        Approval.organization_id == principal.organization_id, Approval.status == ApprovalStatus.PENDING)) or 0
    customers = db.scalar(select(func.count()).select_from(Customer).where(
        Customer.organization_id == principal.organization_id)) or 0
    avg_latency = db.scalar(select(func.avg(MetricEvent.latency_ms)).where(
        MetricEvent.organization_id == principal.organization_id)) or 0
    return templates.TemplateResponse(request, "dashboard.html", {"tickets": tickets, "pending": pending,
                                      "customers": customers, "avg_latency": avg_latency, "principal": principal})


@app.get("/intake", response_class=HTMLResponse)
def intake_form(request: Request):
    return templates.TemplateResponse(request, "intake.html", {})


@app.post("/intake")
def intake_submit(request: Request, name: str = Form(), email: str = Form(), phone: str = Form(""),
                  address: str = Form(), message: str = Form(), requested_window: str = Form(""),
                  db: Session = Depends(get_db)):
    rate_limiter.check(f"intake:{request.client.host if request.client else 'unknown'}", 12)
    ticket = create_intake(db, ServiceRequest(name=name, email=email, phone=phone or None, address=address,
                           message=message, requested_window=requested_window or None), demo_org_id(db))
    return templates.TemplateResponse(request, "submitted.html", {"ticket": ticket})


@app.post("/api/v1/intakes", status_code=201)
def api_intake(request: Request, payload: ServiceRequest, db: Session = Depends(get_db)):
    principal = require_principal(request, db)
    rate_limiter.check(f"api:{principal.user_id}", settings.rate_limit_per_minute)
    ticket = create_intake(db, payload, principal.organization_id)
    return {"id": ticket.id, "reference": ticket.reference, "status": ticket.status,
            "approval_required": True, "risk_flags": ticket.risk_flags}


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    principal = current_principal(request, db)
    if not principal:
        return RedirectResponse("/login", status_code=303)
    ticket = load_ticket(db, ticket_id, principal.organization_id)
    events = db.scalars(select(AuditEvent).where(AuditEvent.ticket_id == ticket_id,
                       AuditEvent.organization_id == principal.organization_id).order_by(AuditEvent.created_at.desc())).all()
    return templates.TemplateResponse(request, "ticket.html", {"ticket": ticket, "events": events,
                                      "principal": principal})


@app.post("/approvals/{approval_id}/{decision}")
def approval_decision(request: Request, approval_id: str, decision: str, note: str = Form(""),
                      db: Session = Depends(get_db)):
    principal = require_principal(request, db, {"admin", "operator"})
    approval = db.scalar(select(Approval).options(selectinload(Approval.ticket)).where(
        Approval.id == approval_id, Approval.organization_id == principal.organization_id))
    if not approval or decision not in {"approve", "reject"}:
        raise HTTPException(404, "Approval not found")
    ticket = decide_approval(db, approval, decision == "approve", principal.email, note)
    enqueue_webhook(ticket.id)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=303)


@app.post("/api/v1/approvals/{approval_id}/{decision}")
def api_approval(request: Request, approval_id: str, decision: str, payload: Decision,
                 db: Session = Depends(get_db)):
    principal = require_principal(request, db, {"admin", "operator"})
    approval = db.scalar(select(Approval).options(selectinload(Approval.ticket)).where(
        Approval.id == approval_id, Approval.organization_id == principal.organization_id))
    if not approval or decision not in {"approve", "reject"}:
        raise HTTPException(404, "Approval not found")
    ticket = decide_approval(db, approval, decision == "approve", principal.email, payload.note)
    enqueue_webhook(ticket.id)
    return {"ticket_id": ticket.id, "status": ticket.status}


@app.get("/tickets/{ticket_id}/quote.pdf")
def quote(request: Request, ticket_id: str, db: Session = Depends(get_db)):
    principal = require_principal(request, db)
    ticket = load_ticket(db, ticket_id, principal.organization_id)
    path = generate_quote(ticket)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/api/v1/metrics")
def metrics(request: Request, db: Session = Depends(get_db)):
    principal = require_principal(request, db, {"admin"})
    rows = db.scalars(select(MetricEvent).where(MetricEvent.organization_id == principal.organization_id)).all()
    return {"calls": len(rows), "success_rate": sum(row.success for row in rows) / len(rows) if rows else 1,
            "average_latency_ms": sum(row.latency_ms for row in rows) / len(rows) if rows else 0,
            "estimated_cost": sum(row.estimated_cost for row in rows)}


@app.post("/api/v1/evaluations")
def evaluate(request: Request, db: Session = Depends(get_db)):
    require_principal(request, db, {"admin"})
    return run_evaluation(get_provider(settings))


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail, "timestamp": datetime.now(timezone.utc).isoformat()}, status_code=exc.status_code)
