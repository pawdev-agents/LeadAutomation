from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from ..models import Appointment, Followup, Lead, User
from ..schemas import AppointmentCreateIn, AppointmentUpdateIn
from ..services.appointments import create_booking
router=APIRouter(prefix="/appointments",tags=["appointments"])
def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def owned(db,id,team):
    row=db.scalar(select(Appointment).join(Lead).where(Appointment.id==id,Lead.team_id==team))
    if not row:raise HTTPException(404,"Appointment not found")
    return row
def out(x):return {"id":x.id,"lead_id":x.lead_id,"starts_at":x.starts_at,"ends_at":x.ends_at,"timezone":x.timezone,"status":x.status,"cancelled_at":x.cancelled_at}
@router.get("")
def list_appointments(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,status:str|None=None,lead_id:int|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(current_user)):
    stmt=select(Appointment).join(Lead).where(Lead.team_id==user.team_id)
    if from_:stmt=stmt.where(Appointment.starts_at>=from_)
    if to:stmt=stmt.where(Appointment.starts_at<=to)
    if status:stmt=stmt.where(Appointment.status==status)
    if lead_id:stmt=stmt.where(Appointment.lead_id==lead_id)
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return {"items":[out(x) for x in db.scalars(stmt.order_by(Appointment.starts_at).offset((page-1)*page_size).limit(page_size))],"total":total,"page":page,"page_size":page_size}
@router.post("",status_code=201)
def create(data:AppointmentCreateIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead=db.scalar(select(Lead).where(Lead.id==data.lead_id,Lead.team_id==user.team_id))
    if not lead:raise HTTPException(404,"Lead not found")
    end=data.ends_at or data.starts_at+timedelta(hours=1)
    item=create_booking(db,lead,data.starts_at,end,data.timezone,user.id);db.commit();db.refresh(item);return out(item)
@router.patch("/{appointment_id}")
def update(appointment_id:int,data:AppointmentUpdateIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=owned(db,appointment_id,user.team_id)
    if item.status=="cancelled":raise HTTPException(400,"Cancelled appointments cannot be changed")
    if data.status=="cancelled":
        item.status="cancelled";item.cancelled_at=datetime.now(timezone.utc)
        for f in db.scalars(select(Followup).where(Followup.lead_id==item.lead_id,Followup.kind.like("appointment_reminder%"),Followup.sent_at.is_(None),Followup.cancelled_at.is_(None))):f.cancelled_at=item.cancelled_at
    else:
        if data.starts_at:
            duration = utc(item.ends_at) - utc(item.starts_at)
            item.starts_at=data.starts_at
            if data.ends_at is None: item.ends_at=data.starts_at + duration
        if data.ends_at:item.ends_at=data.ends_at
        if utc(item.ends_at)<=utc(item.starts_at):raise HTTPException(422,"ends_at must be after starts_at")
        for f in db.scalars(select(Followup).where(Followup.lead_id==item.lead_id,Followup.kind.like("appointment_reminder%"),Followup.sent_at.is_(None),Followup.cancelled_at.is_(None))):
            hours=24 if "24h" in f.kind else 1;f.scheduled_for=item.starts_at-timedelta(hours=hours)
    db.commit();db.refresh(item);return out(item)
