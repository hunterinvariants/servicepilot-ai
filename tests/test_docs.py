def test_branded_api_reference_loads(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "@scalar/api-reference" in response.text
    assert "ServicePilot AI API" in response.text
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]


def test_openapi_schema_remains_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "ServicePilot AI"
