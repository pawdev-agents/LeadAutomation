from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ..models import Followup, Lead, LeadEvent, LeadSource, LeadStatus, User

def score(data):
    points=0
    points += 30 if (data.budget or 0) >= 5000 else 10 if data.budget else 0
    points += {"urgent":30,"high":20,"medium":10}.get((data.urgency or "").lower(),0)
    points += {"referral":20,"google":15,"facebook":10}.get((data.source or "").lower(),5)
    points += 10 if data.service_type else 0
    return min(100, points)

def event(db, lead_id, type, payload=None, actor_id=None): db.add(LeadEvent(lead_id=lead_id,event_type=type,payload=payload or {},actor_id=actor_id))

def owner_for(db, team_id):
    users=db.scalars(select(User).where(User.team_id==team_id, User.active==True).order_by(User.id)).all()
    if not users:return None
    count=db.query(Lead).filter(Lead.team_id==team_id).count()
    return users[count % len(users)].id

def source_for(db, team_id, name):
    source=db.scalar(select(LeadSource).where(LeadSource.team_id==team_id, LeadSource.name==name))
    if not source: source=LeadSource(team_id=team_id,name=name); db.add(source); db.flush()
    return source

def create_lead(db:Session, team_id:int, data, actor_id=None):
    filters=[]
    if data.email: filters.append(Lead.email==str(data.email).lower())
    if data.phone: filters.append(Lead.phone==data.phone)
    duplicate=db.scalar(select(Lead).where(Lead.team_id==team_id, or_(*filters))) if filters else None
    if duplicate: return duplicate, True
    src=source_for(db,team_id,data.source)
    lead=Lead(team_id=team_id,source_id=src.id,owner_id=owner_for(db,team_id),name=data.name,email=str(data.email).lower() if data.email else None,phone=data.phone,budget=data.budget,service_type=data.service_type,urgency=data.urgency,score=score(data),utm={k:v for k,v in {"source":data.utm_source,"medium":data.utm_medium,"campaign":data.utm_campaign}.items() if v})
    db.add(lead); db.flush(); event(db,lead.id,"lead_created",{"source":data.source,"score":lead.score},actor_id)
    now=datetime.now(timezone.utc)
    for kind, when in [("auto_reply",now),("followup_day_1",now+timedelta(days=1)),("followup_day_3",now+timedelta(days=3)),("followup_day_7",now+timedelta(days=7))]:
        db.add(Followup(lead_id=lead.id,kind=kind,scheduled_for=when,idempotency_key=f"lead:{lead.id}:{kind}"))
    return lead, False
