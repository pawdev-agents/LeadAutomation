from datetime import datetime, timedelta, timezone
import pytest
from app.database import Base
from app.models import Appointment, Lead, LeadEvent, LeadSource, LeadStatus
from tests.test_auth import TestingSession, client, engine, register

@pytest.fixture(autouse=True)
def reset(): Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield
def headers(a):return {"Authorization":f"Bearer {a['access_token']}"}
def seed(account):
    now=datetime.now(timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0);db=TestingSession()
    google=LeadSource(team_id=account["team_id"],name="Google");web=LeadSource(team_id=account["team_id"],name="Web");db.add_all([google,web]);db.flush()
    hot=Lead(team_id=account["team_id"],source_id=google.id,name="Hot",email="hot@example.com",status=LeadStatus.new,score=90,created_at=now-timedelta(days=2))
    won=Lead(team_id=account["team_id"],source_id=web.id,name="Won",email="won@example.com",status=LeadStatus.won,score=50,created_at=now-timedelta(days=1))
    qualified=Lead(team_id=account["team_id"],source_id=google.id,name="Qual",email="qual@example.com",status=LeadStatus.qualified,score=60,created_at=now);db.add_all([hot,won,qualified]);db.flush();db.add(LeadEvent(lead_id=qualified.id,event_type="contacted",created_at=now+timedelta(minutes=30)));db.add(Appointment(lead_id=qualified.id,starts_at=now,ends_at=now+timedelta(hours=1)));db.commit();db.close();return now
def test_overview_counts_zero_days_attention_and_today_appointment():
    a=register().json();now=seed(a);data=client.get("/api/stats/overview",params={"from":(now-timedelta(days=3)).isoformat(),"to":(now+timedelta(days=1)).isoformat()},headers=headers(a)).json()
    assert data["totals"]["total_leads"]==3 and data["totals"]["hot_leads"]==1 and data["totals"]["won"]==1
    assert data["conversion_rate"]==33.3 and len(data["leads_per_day"])==5 and any(x["count"]==0 for x in data["leads_per_day"])
    assert len(data["needs_attention"])==1 and len(data["todays_appointments"])==1
def test_weekly_empty_and_isolation():
    a=register().json();b=register("Beta","beta@beta.com").json();empty=client.get("/api/stats/weekly",headers=headers(a)).json()
    assert empty["booking_rate"]==0 and empty["avg_first_response_minutes"] is None
    assert client.get("/api/stats/overview",headers=headers(b)).json()["totals"]["total_leads"]==0
