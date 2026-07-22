from fastapi import Request
from fastapi.responses import HTMLResponse

from app.application import app
from app.main import templates


@app.get("/about", include_in_schema=False, response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "about.html", {})


@app.get("/privacy", include_in_schema=False, response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {})


@app.get("/terms", include_in_schema=False, response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse(request, "terms.html", {})


@app.get("/contact", include_in_schema=False, response_class=HTMLResponse)
def contact(request: Request):
    return templates.TemplateResponse(request, "contact.html", {})

