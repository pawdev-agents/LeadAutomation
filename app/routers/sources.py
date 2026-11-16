from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..config import settings
from ..database import get_db
from ..models import Lead, LeadSource, LeadStatus, User
from ..schemas import SourceIn, SourceUpdateIn

router = APIRouter(prefix="/sources", tags=["sources"])
def get_source(db, source_id, team_id):
    item = db.scalar(select(LeadSource).where(LeadSource.id == source_id, LeadSource.team_id == team_id))
    if not item: raise HTTPException(404, "Source not found")
    return item
def output(source: LeadSource):
    encoded = source.name.lower().replace(" ", "-")
    return {"id":source.id,"name":source.name,"type":source.source_type,"utm_defaults":source.utm_defaults or {},"public_capture_path":f"/public/{source.team_id}/capture","webhook_path":f"/webhooks/{source.team_id}/{encoded}"}
@router.get("")
def list_sources(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [output(item) for item in db.scalars(select(LeadSource).where(LeadSource.team_id == user.team_id).order_by(LeadSource.name))]
@router.post("", status_code=201)
def create_source(data: SourceIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if db.scalar(select(LeadSource).where(LeadSource.team_id == user.team_id, LeadSource.name == data.name)): raise HTTPException(409, "Source already exists")
    item = LeadSource(team_id=user.team_id, name=data.name, source_type=data.source_type, utm_defaults=data.utm_defaults)
    db.add(item); db.commit(); db.refresh(item); return output(item)
@router.patch("/{source_id}")
def update_source(source_id: int, data: SourceUpdateIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = get_source(db, source_id, user.team_id)
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return output(item)
@router.get("/{source_id}/stats")
def stats(source_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = get_source(db, source_id, user.team_id)
    base = select(Lead).where(Lead.team_id == user.team_id, Lead.source_id == item.id)
    leads = db.scalars(base).all(); count=len(leads); booked=sum(x.status in (LeadStatus.booked, LeadStatus.won) for x in leads)
    return {"source_id":item.id,"lead_count":count,"hot_lead_count":sum(x.score >= 80 for x in leads),"booked_count":booked,"conversion_rate":round(booked / count * 100, 1) if count else 0}
