from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Appointment, Lead, LeadEvent, LeadSource, LeadStatus, Team

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


def dt(day, hour=0, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)


def register(team, email):
    response = client.post(
        "/auth/register",
        json={"team_name": team, "name": "Admin", "email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def team_id(name):
    with TestingSession() as db:
        return db.scalar(select(Team.id).where(Team.name == name))


def seed_alpha():
    """Current week (Nov 9-15): L1-L4. Previous week (Nov 2-8): P1, P2."""
    tid = team_id("Alpha")
    with TestingSession() as db:
        web = LeadSource(team_id=tid, name="website")
        ads = LeadSource(team_id=tid, name="ads")
        db.add_all([web, ads])
        db.flush()

        def lead(name, created, status, score, source):
            item = Lead(
                team_id=tid,
                source_id=source.id,
                name=name,
                status=status,
                score=score,
                created_at=created,
                updated_at=created,
            )
            db.add(item)
            db.flush()
            return item

        def contacted(item, when):
            db.add(LeadEvent(lead_id=item.id, event_type="contacted", created_at=when))

        l1 = lead("L1", dt(9, 10), LeadStatus.new, 90, web)
        l2 = lead("L2", dt(10, 10), LeadStatus.contacted, 50, web)
        contacted(l2, dt(10, 10, 30))  # 30 min
        l3 = lead("L3", dt(11, 9), LeadStatus.booked, 85, ads)
        contacted(l3, dt(11, 10))  # 60 min
        l4 = lead("L4", dt(12, 9), LeadStatus.won, 70, ads)
        contacted(l4, dt(12, 10, 30))  # 90 min
        lead("P1", dt(3, 10), LeadStatus.new, 10, web)
        p2 = lead("P2", dt(4, 10), LeadStatus.contacted, 40, web)
        contacted(p2, dt(4, 12))  # 120 min
        ids = {"L1": l1.id, "L2": l2.id, "L3": l3.id, "L4": l4.id}
        db.commit()
    return ids


def add_appointments(ids):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with TestingSession() as db:
        db.add(Appointment(
            lead_id=ids["L2"],
            starts_at=today + timedelta(hours=1),
            ends_at=today + timedelta(hours=2),
            status="scheduled",
        ))
        db.add(Appointment(
            lead_id=ids["L3"],
            starts_at=today + timedelta(hours=3),
            ends_at=today + timedelta(hours=4),
            status="cancelled",
        ))
        db.commit()


WEEK_RANGE = {"from": "2026-11-09T00:00:00Z", "to": "2026-11-15T23:59:59Z"}


def test_stats_require_auth():
    assert client.get("/api/stats/overview").status_code in (401, 403)
    assert client.get("/api/stats/weekly").status_code in (401, 403)


def test_overview_known_dataset():
    headers = register("Alpha", "admin@alpha-team.com")
    seed_alpha()
    data = client.get("/api/stats/overview", params=WEEK_RANGE, headers=headers).json()

    totals = data["totals"]
    assert totals["total_leads"] == 4
    assert totals["hot_leads"] == 2
    assert totals["qualified"] == 0
    assert totals["booked"] == 1
    assert totals["won"] == 1
    assert totals["lost"] == 0
    assert isinstance(totals["new_this_week"], int)
    assert data["conversion_rate"] == 25.0

    per_day = {d["date"]: d["count"] for d in data["leads_per_day"]}
    assert per_day == {
        "2026-11-09": 1,
        "2026-11-10": 1,
        "2026-11-11": 1,
        "2026-11-12": 1,
        "2026-11-13": 0,
        "2026-11-14": 0,
        "2026-11-15": 0,
    }
    assert {x["source"]: x["count"] for x in data["leads_by_source"]} == {"website": 2, "ads": 2}
    assert [(x["status"], x["count"]) for x in data["funnel"]] == [
        ("new", 1), ("contacted", 1), ("qualified", 0), ("booked", 1), ("won", 1), ("lost", 0),
    ]


def test_overview_empty_team():
    headers = register("Beta", "admin@beta-team.com")
    data = client.get("/api/stats/overview", headers=headers).json()
    assert data["totals"]["total_leads"] == 0
    assert data["totals"]["hot_leads"] == 0
    assert data["conversion_rate"] == 0
    assert len(data["leads_per_day"]) == 30
    assert all(d["count"] == 0 for d in data["leads_per_day"])
    assert data["leads_by_source"] == []
    assert [x["count"] for x in data["funnel"]] == [0, 0, 0, 0, 0, 0]
    assert data["needs_attention"] == []
    assert data["todays_appointments"] == []


def test_needs_attention_and_todays_appointments():
    headers = register("Alpha", "admin@alpha-team.com")
    ids = seed_alpha()
    add_appointments(ids)
    data = client.get("/api/stats/overview", headers=headers).json()
    # L1 is hot, still "new", older than 24h, never contacted. L3 is booked.
    assert [x["id"] for x in data["needs_attention"]] == [ids["L1"]]
    # L2 is scheduled today; L3's appointment today is cancelled.
    assert [x["lead_id"] for x in data["todays_appointments"]] == [ids["L2"]]


def test_weekly_known_dataset():
    headers = register("Alpha", "admin@alpha-team.com")
    seed_alpha()
    data = client.get("/api/stats/weekly", params={"week_start": "2026-11-09"}, headers=headers).json()

    assert {x["source"]: x["count"] for x in data["leads_per_source"]} == {"website": 2, "ads": 2}
    assert data["avg_first_response_minutes"] == 60.0
    assert data["booking_rate"] == 50.0
    assert {x["status"]: x["share"] for x in data["conversion_by_stage"]} == {
        "new": 25.0, "contacted": 25.0, "booked": 25.0, "won": 25.0,
    }
    change = data["change_vs_previous_week"]
    assert change["total_leads"] == {"absolute": 2, "percent": 100.0}
    assert change["booking_rate"] == {"absolute": 50.0, "percent": None}
    assert change["avg_response_time"] == {"absolute": -60.0, "percent": -50.0}


def test_weekly_previous_week_empty_gives_nulls():
    headers = register("Alpha", "admin@alpha-team.com")
    seed_alpha()
    data = client.get("/api/stats/weekly", params={"week_start": "2026-11-02"}, headers=headers).json()
    assert data["booking_rate"] == 0.0
    assert data["avg_first_response_minutes"] == 120.0
    empty = {"absolute": None, "percent": None}
    change = data["change_vs_previous_week"]
    assert change["total_leads"] == empty
    assert change["booking_rate"] == empty
    assert change["avg_response_time"] == empty


def test_weekly_empty_team():
    headers = register("Beta", "admin@beta-team.com")
    data = client.get("/api/stats/weekly", headers=headers).json()
    assert data["leads_per_source"] == []
    assert data["avg_first_response_minutes"] is None
    assert data["booking_rate"] == 0
    assert data["conversion_by_stage"] == []
    empty = {"absolute": None, "percent": None}
    change = data["change_vs_previous_week"]
    assert change["total_leads"] == empty
    assert change["booking_rate"] == empty
    assert change["avg_response_time"] == empty


def test_stats_team_isolation():
    alpha = register("Alpha", "admin@alpha-team.com")
    beta = register("Beta", "admin@beta-team.com")
    seed_alpha()

    alpha_overview = client.get("/api/stats/overview", params=WEEK_RANGE, headers=alpha).json()
    beta_overview = client.get("/api/stats/overview", params=WEEK_RANGE, headers=beta).json()
    assert alpha_overview["totals"]["total_leads"] == 4
    assert beta_overview["totals"]["total_leads"] == 0
    assert beta_overview["needs_attention"] == []

    beta_weekly = client.get("/api/stats/weekly", params={"week_start": "2026-11-09"}, headers=beta).json()
    assert beta_weekly["leads_per_source"] == []
    assert beta_weekly["avg_first_response_minutes"] is None


