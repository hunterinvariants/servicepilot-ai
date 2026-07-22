import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-with-sufficient-length"
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "secure-test-password"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.site import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture
def authenticated_client(client):
    response = client.post("/login", data={"email": "admin@test.local", "password": "secure-test-password"})
    assert response.status_code == 200
    return client

