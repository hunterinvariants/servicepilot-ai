from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class ServiceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = None
    address: str = Field(min_length=5, max_length=300)
    message: str = Field(min_length=10, max_length=5000)
    requested_window: str | None = Field(default=None, max_length=120)
    source: Literal["web", "chat", "email", "api"] = "web"


class IntakeResult(BaseModel):
    category: str
    summary: str
    urgency: Literal["low", "medium", "high", "emergency"]
    confidence: float = Field(ge=0, le=1)
    requested_window: str | None = None
    risk_flags: list[str] = []
    quote_amount: float | None = None
    response_draft: str


class Decision(BaseModel):
    decided_by: str = Field(min_length=2, max_length=160)
    note: str = Field(default="", max_length=1000)

