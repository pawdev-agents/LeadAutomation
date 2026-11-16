from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from ..models import Followup, Lead, User
from ..schemas import FollowupCreateIn
router=APIRouter(tags=["followups"])
def lead(db,id,team):
    item=db.scalar(select(Lead).where(Lead.id==id,Lead.team_id==team))
    if not item:raise HTTPException(404,"Lead not found")
    return item
def out(x):return {"id":x.id,"lead_id":x.lead_id,"kind":x.kind,"channel":x.channel,"subject":x.subject,"body":x.body,"due_at":x.scheduled_for,"sent_at":x.sent_at,"cancelled_at":x.cancelled_at}
@router.get("/leads/{lead_id}/followups")
def list_followups(lead_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead(db,lead_id,user.team_id);return [out(x) for x in db.scalars(select(Followup).where(Followup.lead_id==lead_id).order_by(Followup.scheduled_for))]
@router.post("/leads/{lead_id}/followups",status_code=201)
def create(lead_id:int,data:FollowupCreateIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead(db,lead_id,user.team_id);item=Followup(lead_id=lead_id,kind="manual",channel=data.channel,subject=data.subject,body=data.body,scheduled_for=data.due_at,idempotency_key=f"manual:{lead_id}:{data.due_at.timestamp()}");db.add(item);db.commit();db.refresh(item);return out(item)
@router.patch("/followups/{followup_id}")
def cancel(followup_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.scalar(select(Followup).join(Lead).where(Followup.id==followup_id,Lead.team_id==user.team_id))
    if not item:raise HTTPException(404,"Follow-up not found")
    if item.sent_at:raise HTTPException(400,"Sent follow-ups cannot be cancelled")
    item.cancelled_at=datetime.now(timezone.utc);db.commit();return out(item)
