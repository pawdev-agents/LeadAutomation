import pytest
from app.database import Base
from tests.test_auth import client, engine, register

@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

def headers(account): return {"Authorization": f"Bearer {account['access_token']}"}
def add_lead(auth, name, email, budget=0):
    response=client.post("/api/leads",headers=auth,json={"name":name,"email":email,"source":"Google","budget":budget})
    assert response.status_code==201
    return response.json()

def test_filters_search_pagination_sorting_and_notes():
    account=register().json(); auth=headers(account)
    first=add_lead(auth,"Zara Search","zara@alpha.com",9000);add_lead(auth,"Adam Search","adam@alpha.com",100)
    page=client.get("/api/leads?q=search&sort=score&page=1&page_size=1",headers=auth).json()
    assert page["total"]==2 and page["items"][0]["name"]=="Adam Search"
    assert client.get("/api/leads?min_score=40",headers=auth).json()["total"]==1
    assert client.post(f"/api/leads/{first['id']}/notes",headers=auth,json={"text":"Called today"}).status_code==201
    assert client.get(f"/api/leads/{first['id']}/events",headers=auth).json()[0]["event_type"]=="note"

def test_cross_team_owner_users_and_sources():
    one=register("One","one@alpha.com").json();two=register("Two","two@beta.com").json();auth=headers(one)
    created=add_lead(auth,"Private","private@alpha.com")
    assert client.patch(f"/api/leads/{created['id']}",headers=auth,json={"owner_id":two["user"]["id"]}).status_code==400
    member=client.post("/api/users",headers=auth,json={"name":"Member","email":"member@alpha.com","password":"password123","role":"member"})
    assert member.status_code==201 and "password_hash" not in member.json()
    token=client.post("/auth/login",json={"email":"member@alpha.com","password":"password123"}).json()
    assert client.post("/api/users",headers=headers(token),json={"name":"Nope","email":"nope@alpha.com","password":"password123"}).status_code==403
    source=client.post("/api/sources",headers=auth,json={"name":"Partner","source_type":"referral"}).json()
    assert source["public_capture_path"]==f"/public/{one['team_id']}/capture"
    response=client.post("/api/leads",headers=auth,json={"name":"Partner hot","email":"hot@alpha.com","source":"Partner","budget":9000,"urgency":"urgent"})
    assert response.status_code==201
    stats=client.get(f"/api/sources/{source['id']}/stats",headers=auth).json()
    assert stats["lead_count"]==1 and stats["hot_lead_count"]==0
    assert client.get(f"/api/sources/{source['id']}/stats",headers=headers(two)).status_code==404
