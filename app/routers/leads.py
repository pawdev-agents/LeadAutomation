from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from ..models import Lead, LeadEvent, LeadStatus, User
from ..schemas import LeadIn, LeadOut, LeadUpdate, NoteIn
from ..services.leads import create_lead, event, score
router=APIRouter(prefix="/leads",tags=["leads"])
ALLOWED_TRANSITIONS={
    LeadStatus.new:{LeadStatus.contacted,LeadStatus.qualified,LeadStatus.lost},
    LeadStatus.contacted:{LeadStatus.qualified,LeadStatus.booked,LeadStatus.lost},
    LeadStatus.qualified:{LeadStatus.booked,LeadStatus.won,LeadStatus.lost},
    LeadStatus.booked:{LeadStatus.won,LeadStatus.lost},
    LeadStatus.won:set(), LeadStatus.lost:set(),
}
@router.get("")
def list_leads(status:LeadStatus|None=None, source:int|None=None, owner_id:int|None=None, min_score:int|None=None, q:str|None=None, sort:str="-created_at", page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100), db:Session=Depends(get_db), user:User=Depends(current_user)):
    stmt=select(Lead).where(Lead.team_id==user.team_id)
    if status:stmt=stmt.where(Lead.status==status)
    if source:stmt=stmt.where(Lead.source_id==source)
    if owner_id:stmt=stmt.where(Lead.owner_id==owner_id)
    if min_score is not None:stmt=stmt.where(Lead.score>=min_score)
    if q:
        term=f"%{q.lower()}%";stmt=stmt.where(or_(func.lower(Lead.name).like(term),func.lower(Lead.email).like(term),func.lower(Lead.phone).like(term)))
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    field={"created_at":Lead.created_at,"updated_at":Lead.updated_at,"score":Lead.score}.get(sort.lstrip("-"),Lead.created_at)
    items=db.scalars(stmt.order_by(field.desc() if sort.startswith("-") else field.asc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":[LeadOut.model_validate(x).model_dump(mode="json") for x in items],"total":total,"page":page,"page_size":page_size}
@router.post("",response_model=LeadOut,status_code=201)
def create(data:LeadIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead, duplicate=create_lead(db,user.team_id,data,user.id)
    if duplicate: raise HTTPException(409,"A matching lead already exists")
    db.commit(); db.refresh(lead); return lead
@router.get("/{lead_id}",response_model=LeadOut)
def get(lead_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead=db.scalar(select(Lead).where(Lead.id==lead_id,Lead.team_id==user.team_id))
    if not lead:raise HTTPException(404,"Lead not found")
    return lead
@router.get("/{lead_id}/events")
def events(lead_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    get(lead_id,db,user)
    return [{"id":x.id,"event_type":x.event_type,"payload":x.payload,"actor_id":x.actor_id,"created_at":x.created_at} for x in db.scalars(select(LeadEvent).where(LeadEvent.lead_id==lead_id).order_by(LeadEvent.created_at.desc()))]
@router.post("/{lead_id}/notes",status_code=201)
def note(lead_id:int,data:NoteIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    get(lead_id,db,user);event(db,lead_id,"note",{"text":data.text},user.id);db.commit();return {"ok":True}
@router.patch("/{lead_id}",response_model=LeadOut)
def update(lead_id:int,data:LeadUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead=db.scalar(select(Lead).where(Lead.id==lead_id,Lead.team_id==user.team_id))
    if not lead:raise HTTPException(404,"Lead not found")
    old=lead.status
    old_owner=lead.owner_id
    if data.owner_id is not None and not db.scalar(select(User).where(User.id==data.owner_id,User.team_id==user.team_id)):
        raise HTTPException(400,"Owner must belong to this team")
    if data.status and data.status != old and data.status not in ALLOWED_TRANSITIONS[old]:
        raise HTTPException(422,f"Invalid status transition: {old.value} → {data.status.value}")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(lead,k,v)
    if any(k in data.model_fields_set for k in ("budget","service_type","urgency")): lead.score=score(type("D",(),{**lead.__dict__,"source":"manual"})())
    if data.status and old != data.status:event(db,lead.id,"status_changed",{"from":old.value,"to":data.status.value},user.id)
    if data.owner_id is not None and old_owner != data.owner_id:event(db,lead.id,"owner_changed",{"from":old_owner,"to":data.owner_id},user.id)
    db.commit();db.refresh(lead);return lead
