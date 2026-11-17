from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ..models import Followup, Lead, LeadEvent, LeadSource, LeadStatus, Team, User
from .team_settings import merged

DEFAULT_WEIGHTS = {
    "budget_high": 30,
    "budget_low": 10,
    "urgency_urgent": 30,
    "urgency_high": 20,
    "urgency_medium": 10,
    "source_referral": 20,
    "source_google": 15,
    "source_facebook": 10,
    "source_other": 5,
    "service_type": 10,
}


def score(data, weights=None):
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    points = 0
    budget = data.budget or 0
    if budget >= 5000:
        points += w["budget_high"]
    elif budget:
        points += w["budget_low"]
    urgency = {"urgent": w["urgency_urgent"], "high": w["urgency_high"], "medium": w["urgency_medium"]}
    points += urgency.get((data.urgency or "").lower(), 0)
    sources = {"referral": w["source_referral"], "google": w["source_google"], "facebook": w["source_facebook"]}
    points += sources.get((data.source or "").lower(), w["source_other"])
    if data.service_type:
        points += w["service_type"]
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
    lead=Lead(team_id=team_id,source_id=src.id,owner_id=owner_for(db,team_id),name=data.name,email=str(data.email).lower() if data.email else None,phone=data.phone,budget=data.budget,service_type=data.service_type,urgency=data.urgency,score=score(data,merged(db.get(Team,team_id))["scoring_weights"]),utm={k:v for k,v in {"source":data.utm_source,"medium":data.utm_medium,"campaign":data.utm_campaign}.items() if v})
    db.add(lead); db.flush(); event(db,lead.id,"lead_created",{"source":data.source,"score":lead.score},actor_id)
    now=datetime.now(timezone.utc)
    delays=merged(db.get(Team,team_id))["followup_delays_days"]
    for kind, when in [("auto_reply",now)]+[(f"followup_day_{d}",now+timedelta(days=d)) for d in delays]:
        db.add(Followup(lead_id=lead.id,kind=kind,scheduled_for=when,idempotency_key=f"lead:{lead.id}:{kind}"))
    return lead, False
