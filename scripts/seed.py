from sqlalchemy import select

from app.auth import hash_secret
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import ApiKey, Organization, Technician, Ticket, User
from app.schemas import ServiceRequest
from app.workflow import create_intake


def main():
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.slug == "servicepilot-demo"))
        if not org:
            org = Organization(name="ServicePilot Demo", slug="servicepilot-demo")
            db.add(org)
            db.flush()
        if not db.scalar(select(User).where(User.email == settings.admin_email)):
            db.add(User(organization_id=org.id, email=settings.admin_email,
                        password_hash=hash_secret(settings.admin_password), role="admin"))
        if not db.scalar(select(ApiKey).where(ApiKey.organization_id == org.id)):
            db.add(ApiKey(organization_id=org.id, name="Demo API", prefix=settings.api_key[:12],
                          key_hash=hash_secret(settings.api_key)))
        if not db.scalar(select(Technician).where(Technician.organization_id == org.id)):
            db.add_all([
                Technician(organization_id=org.id, name="Maya Keller", email="maya@servicepilot.demo", skills=["plumbing", "hvac"], region="Zürich"),
                Technician(organization_id=org.id, name="Luca Frei", email="luca@servicepilot.demo", skills=["electrical", "appliance"], region="Zürich"),
                Technician(organization_id=org.id, name="Nina Baumann", email="nina@servicepilot.demo", skills=["general", "hvac"], region="Winterthur"),
            ])
        db.commit()
        if not db.scalar(select(Ticket).where(Ticket.organization_id == org.id)):
            create_intake(db, ServiceRequest(name="Sofia Meier", email="sofia@example.com", phone="+41 79 555 01 02",
                address="24 Seefeldstrasse, Zürich", message="The kitchen pipe is leaking steadily under the sink. Please come Friday morning.", requested_window="Friday morning"), org.id)
            create_intake(db, ServiceRequest(name="Jonas Weber", email="jonas@example.com", address="8 Marktgasse, Zürich",
                message="Urgent: there is a sparking socket in the bedroom. We switched off the breaker."), org.id)
    print(f"Demo ready. Sign in as {settings.admin_email}; API key prefix: {settings.api_key[:12]}")


if __name__ == "__main__":
    main()
