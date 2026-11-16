import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# A file-backed SQLite test database remains visible to TestClient worker threads.
engine = create_engine("sqlite:///./data/test_suite.db", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


def register(team="Alpha", email="admin@alpha.com", password="password123"):
    return client.post(
        "/auth/register",
        json={"team_name": team, "name": "Admin", "email": email, "password": password},
    )


def test_register_login_and_me():
    response = register()
    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["role"] == "admin"
    login = client.post(
        "/auth/login",
        json={"email": "admin@alpha.com", "password": "password123"},
    )
    assert login.status_code == 200
    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["team"]["name"] == "Alpha"


def test_login_rejects_wrong_password_and_invalid_token():
    register()
    wrong = client.post(
        "/auth/login",
        json={"email": "admin@alpha.com", "password": "wrong-password"},
    )
    assert wrong.status_code == 401
    bad_token = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    assert bad_token.status_code == 401


def test_team_isolation_for_leads():
    first = register("Alpha", "admin@alpha.com").json()
    second = register("Beta", "admin@beta.com").json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    create = client.post(
        "/api/leads",
        headers=second_headers,
        json={"name": "Private lead", "email": "private@beta.com", "source": "website"},
    )
    assert create.status_code == 201
    lead_id = create.json()["id"]
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.get("/api/leads", headers=first_headers).json()["items"] == []
    assert client.get(f"/api/leads/{lead_id}", headers=first_headers).status_code == 404
