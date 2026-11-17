import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
client = TestClient(app)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_db():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def register(team, email):
    response = client.post(
        "/auth/register",
        json={"team_name": team, "name": "Admin", "email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_settings_require_auth():
    assert client.get("/api/settings").status_code in (401, 403)


def test_defaults():
    headers = register("Alpha", "admin@alpha-team.com")
    data = client.get("/api/settings", headers=headers).json()
    assert data["team_name"] == "Alpha"
    assert data["followup_delays_days"] == [1, 3, 7]
    assert data["working_hours"]["start"] == "09:00"
    assert data["scoring_weights"] == {}


def test_admin_can_update_and_values_persist():
    headers = register("Alpha", "admin@alpha-team.com")
    body = {
        "timezone": "Asia/Karachi",
        "followup_delays_days": [2, 5, 10],
        "auto_reply_subject": "We got your message",
        "scoring_weights": {"budget": 40, "urgency": 20},
        "working_hours": {"start": "10:00", "end": "18:00", "days": [4, 0, 1]},
    }
    response = client.patch("/api/settings", headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = client.get("/api/settings", headers=headers).json()
    assert data["timezone"] == "Asia/Karachi"
    assert data["followup_delays_days"] == [2, 5, 10]
    assert data["auto_reply_subject"] == "We got your message"
    assert data["scoring_weights"] == {"budget": 40, "urgency": 20}
    assert data["working_hours"] == {"start": "10:00", "end": "18:00", "days": [0, 1, 4]}
    assert "Hi {name}" in data["auto_reply_body"]  # untouched default


@pytest.mark.parametrize("body", [
    {"followup_delays_days": []},
    {"followup_delays_days": [5, 3]},
    {"followup_delays_days": [1, 1]},
    {"followup_delays_days": [0, 3]},
    {"followup_delays_days": [1, 2, 3, 4, 5, 6]},
    {"working_hours": {"start": "25:00", "end": "18:00", "days": [0]}},
    {"working_hours": {"start": "18:00", "end": "09:00", "days": [0]}},
    {"working_hours": {"start": "09:00", "end": "17:00", "days": [7]}},
    {"scoring_weights": {"budget": 101}},
    {"scoring_weights": {"budget": -1}},
    {"unknown_setting": 1},
])
def test_invalid_values_are_rejected(body):
    headers = register("Alpha", "admin@alpha-team.com")
    assert client.patch("/api/settings", headers=headers, json=body).status_code == 422
    # nothing was saved
    assert client.get("/api/settings", headers=headers).json()["followup_delays_days"] == [1, 3, 7]


def test_member_can_read_but_not_change():
    admin_headers = register("Alpha", "admin@alpha-team.com")
    created = client.post(
        "/api/users",
        headers=admin_headers,
        json={"name": "Sam", "email": "sam@alpha-team.com", "password": "password123", "role": "member"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/auth/login", json={"email": "sam@alpha-team.com", "password": "password123"})
    member = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/settings", headers=member).status_code == 200
    assert client.patch("/api/settings", headers=member, json={"auto_reply_subject": "Hi"}).status_code == 403


def test_team_name_must_be_unique():
    alpha = register("Alpha", "admin@alpha-team.com")
    register("Beta", "admin@beta-team.com")
    assert client.patch("/api/settings", headers=alpha, json={"team_name": "Beta"}).status_code == 409
    assert client.patch("/api/settings", headers=alpha, json={"team_name": "Alpha Co"}).status_code == 200


def test_settings_team_isolation():
    alpha = register("Alpha", "admin@alpha-team.com")
    beta = register("Beta", "admin@beta-team.com")
    client.patch("/api/settings", headers=alpha, json={"followup_delays_days": [2, 4]})
    assert client.get("/api/settings", headers=alpha).json()["followup_delays_days"] == [2, 4]
    assert client.get("/api/settings", headers=beta).json()["followup_delays_days"] == [1, 3, 7]
