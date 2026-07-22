from fastapi.responses import HTMLResponse

from app.main import app


# Replace FastAPI's default Swagger route with a modern, branded API reference.
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/docs"]


@app.middleware("http")
async def documentation_security_policy(request, call_next):
    response = await call_next(request)
    if request.url.path == "/docs":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
            "connect-src 'self'"
        )
    return response


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
def api_reference():
    return HTMLResponse("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="ServicePilot AI REST API reference">
  <title>API Reference · ServicePilot AI</title>
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    data-configuration='{"theme":"saturn","layout":"modern","hideModels":false,"darkMode":false,"metaData":{"title":"ServicePilot AI API","description":"Secure, human-approved service operations API"}}'>
  </script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>""")

