from datetime import datetime, timedelta, timezone
import pytest
from app.database import Base
from tests.test_auth import client, engine, register
@pytest.fixture(autouse=True)
def reset(): Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield
def headers(a):return {"Authorization":f"Bearer {a['access_token']}"}
def lead(h):return client.post("/api/leads",headers=h,json={"name":"Book Me","email":"book@alpha.com","source":"Website"}).json()
def test_create_reschedule_cancel_and_reminders():
    a=register().json();h=headers(a);l=lead(h);start=datetime.now(timezone.utc)+timedelta(days=3)
    r=client.post("/api/appointments",headers=h,json={"lead_id":l["id"],"starts_at":start.isoformat()});assert r.status_code==201
    ap=r.json();assert client.get(f"/api/leads/{l['id']}",headers=h).json()["status"]=="booked"
    fs=client.get(f"/api/leads/{l['id']}/followups",headers=h).json();assert len([x for x in fs if "reminder" in x["kind"]])==2
    moved=start+timedelta(days=1);assert client.patch(f"/api/appointments/{ap['id']}",headers=h,json={"starts_at":moved.isoformat()}).status_code==200
    assert client.patch(f"/api/appointments/{ap['id']}",headers=h,json={"status":"cancelled"}).json()["status"]=="cancelled"
    assert client.patch(f"/api/appointments/{ap['id']}",headers=h,json={"starts_at":start.isoformat()}).status_code==400
def test_manual_followup_cancel_and_isolation():
    a=register().json();b=register("Beta","beta@beta.com").json();h=headers(a);l=lead(h);due=datetime.now(timezone.utc)+timedelta(days=1)
    f=client.post(f"/api/leads/{l['id']}/followups",headers=h,json={"channel":"email","subject":"Hi","body":"Body","due_at":due.isoformat()});assert f.status_code==201
    assert client.patch(f"/api/followups/{f.json()['id']}",headers=h).json()["cancelled_at"]
    assert client.get(f"/api/leads/{l['id']}/followups",headers=headers(b)).status_code==404
