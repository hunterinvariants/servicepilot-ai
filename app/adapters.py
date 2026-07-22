from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import Settings
from app.models import Ticket


@dataclass
class DeliveryResult:
    adapter: str
    external_id: str
    status: str


class NotificationAdapter(ABC):
    @abstractmethod
    def send(self, ticket: Ticket) -> DeliveryResult: ...


class WebhookAdapter(NotificationAdapter):
    def __init__(self, url: str, signing_secret: str):
        self.url = url
        self.signing_secret = signing_secret

    def send(self, ticket: Ticket) -> DeliveryResult:
        from app.webhooks import signature
        payload = {"event": "ticket.updated", "ticket_id": ticket.id, "status": ticket.status}
        response = httpx.post(self.url, json=payload, headers={"X-ServicePilot-Signature": signature(payload, self.signing_secret)}, timeout=10)
        response.raise_for_status()
        return DeliveryResult("webhook", response.headers.get("X-Request-ID", ticket.id), "sent")


class CalendarAdapter:
    """Provider-neutral calendar boundary; demo mode records a deterministic booking reference."""

    def reserve(self, ticket: Ticket) -> DeliveryResult:
        return DeliveryResult("calendar-demo", f"cal-{ticket.reference}", "reserved")


class CRMAdapter:
    """Provider-neutral CRM boundary; replace with HubSpot/Salesforce without changing workflow policy."""

    def sync(self, ticket: Ticket) -> DeliveryResult:
        return DeliveryResult("crm-demo", f"crm-{ticket.customer_id}", "synced")


class EmailAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def draft(self, ticket: Ticket) -> DeliveryResult:
        return DeliveryResult("smtp-draft", f"mail-{ticket.reference}-{int(datetime.now().timestamp())}", "drafted")

