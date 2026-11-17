from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.leads import score

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def lead_data(**kw):
    base = dict(budget=6000, urgency="urgent", source="referral", service_type="seo")
    base.update(kw)
    return SimpleNamespace(**base)


def test_default_score():
    assert score(lead_data()) == 90


def test_weight_override_changes_score():
    assert score(lead_data(), {"budget_high": 0}) == 60


def test_score_is_capped_at_100():
    assert score(lead_data(), {"budget_high": 100}) == 100


def test_team_weights_apply_to_new_leads():
    reg = client.post(
        "/auth/register",
        json={"team_name": "Alpha", "name": "Admin", "email": "admin@alpha-team.com", "password": "password123"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    def make(email):
        r = client.post("/api/leads", headers=headers, json={"name": "Lead", "email": email, "source": "website"})
        assert r.status_code == 201, r.text
        return r.json()["score"]

    assert make("a@client-one.com") == 5
    patch = client.patch("/api/settings", headers=headers, json={"scoring_weights": {"source_other": 50}})
    assert patch.status_code == 200, patch.text
    assert make("b@client-two.com") == 50


def test_editing_lead_keeps_source_points():
    reg = client.post(
        "/auth/register",
        json={"team_name": "Beta", "name": "Admin", "email": "admin@beta-team.com", "password": "password123"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    created = client.post(
        "/api/leads",
        headers=headers,
        json={"name": "Lead", "email": "a@client-one.com", "source": "referral"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["score"] == 20
    patched = client.patch(f"/api/leads/{created.json()['id']}", headers=headers, json={"budget": 6000})
    assert patched.status_code == 200, patched.text
    assert patched.json()["score"] == 50
