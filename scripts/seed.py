from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Technician
from app.schemas import ServiceRequest
from app.workflow import create_intake


def main():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.scalar(select(Technician).limit(1)):
            db.add_all([
                Technician(name="Maya Keller", email="maya@servicepilot.demo", skills=["plumbing", "hvac"], region="Zürich"),
                Technician(name="Luca Frei", email="luca@servicepilot.demo", skills=["electrical", "appliance"], region="Zürich"),
                Technician(name="Nina Baumann", email="nina@servicepilot.demo", skills=["general", "hvac"], region="Winterthur"),
            ])
            db.commit()
        if db.query(__import__("app.models", fromlist=["Ticket"]).Ticket).count() == 0:
            create_intake(db, ServiceRequest(name="Sofia Meier", email="sofia@example.com", phone="+41 79 555 01 02",
                address="24 Seefeldstrasse, Zürich", message="The kitchen pipe is leaking steadily under the sink. Please come Friday morning.", requested_window="Friday morning"))
            create_intake(db, ServiceRequest(name="Jonas Weber", email="jonas@example.com", address="8 Marktgasse, Zürich",
                message="Urgent: there is a sparking socket in the bedroom. We switched off the breaker."))
    print("Demo technicians and requests are ready.")


if __name__ == "__main__":
    main()

