from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import worker
from app.database import Base, get_db
from app.main import app
from app.models import Followup, Lead

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


def create_lead(headers, email):
    response = client.post(
        "/api/leads",
        headers=headers,
        json={"name": "Lead", "email": email, "source": "website"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def kinds(lead_id):
    with TestingSession() as db:
        return list(db.scalars(
            select(Followup.kind).where(Followup.lead_id == lead_id).order_by(Followup.scheduled_for, Followup.id)
        ))


def test_default_delays_are_day_1_3_7():
    headers = register("Alpha", "admin@alpha-team.com")
    lead_id = create_lead(headers, "a@client-one.com")
    assert kinds(lead_id) == ["auto_reply", "followup_day_1", "followup_day_3", "followup_day_7"]


def test_custom_delays_apply_to_new_leads_only():
    headers = register("Alpha", "admin@alpha-team.com")
    before = create_lead(headers, "a@client-one.com")
    patch = client.patch("/api/settings", headers=headers, json={"followup_delays_days": [2, 5]})
    assert patch.status_code == 200, patch.text
    after = create_lead(headers, "b@client-two.com")
    assert kinds(before) == ["auto_reply", "followup_day_1", "followup_day_3", "followup_day_7"]
    assert kinds(after) == ["auto_reply", "followup_day_2", "followup_day_5"]


def test_worker_handles_custom_followup_kind(monkeypatch):
    headers = register("Alpha", "admin@alpha-team.com")
    client.patch("/api/settings", headers=headers, json={"followup_delays_days": [2]})
    lead_id = create_lead(headers, "a@client-one.com")
    now = datetime.now(timezone.utc)
    with TestingSession() as db:
        jobs = {j.kind: j for j in db.scalars(select(Followup).where(Followup.lead_id == lead_id))}
        jobs["auto_reply"].cancelled_at = now  # so only the custom follow-up can set last_contacted_at
        jobs["followup_day_2"].scheduled_for = now - timedelta(hours=1)
        db.commit()
    monkeypatch.setattr(worker, "SessionLocal", TestingSession)
    worker.tick()
    with TestingSession() as db:
        assert db.get(Lead, lead_id).last_contacted_at is not None
        job = db.scalar(select(Followup).where(Followup.lead_id == lead_id, Followup.kind == "followup_day_2"))
        assert job.sent_at is not None
