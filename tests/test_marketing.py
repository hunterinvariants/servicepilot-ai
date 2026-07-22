def test_professional_marketing_pages(client):
    homepage = client.get("/")
    assert homepage.status_code == 200
    assert "FIELD SERVICE & PROPERTY OPERATIONS" in homepage.text
    assert "SECURITY BY DESIGN" in homepage.text
    for path in ("/about", "/privacy", "/terms", "/contact"):
        assert client.get(path).status_code == 200
