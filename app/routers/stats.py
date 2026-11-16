from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from ..auth import current_user
from ..database import get_db
from ..models import Appointment, Lead, LeadEvent, LeadSource, LeadStatus, User

router=APIRouter(prefix="/stats",tags=["stats"])
STATUSES=["new","contacted","qualified","booked","won","lost"]
def bounds(start,end):
    start=start or datetime.now(timezone.utc)-timedelta(days=29);end=end or datetime.now(timezone.utc)
    return start,end
@router.get("/overview")
def overview(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
    start,end=bounds(from_,to);base=Lead.team_id==user.team_id
    rows=db.execute(select(Lead.status,func.count()).where(base,Lead.created_at>=start,Lead.created_at<=end).group_by(Lead.status)).all();funnel={x:0 for x in STATUSES};funnel.update({str(s.value if hasattr(s,'value') else s):n for s,n in rows})
    total=sum(funnel.values());today=datetime.now(timezone.utc);week=today-timedelta(days=today.weekday())
    hot=db.scalar(select(func.count()).select_from(Lead).where(base,Lead.created_at>=start,Lead.created_at<=end,Lead.score>=80)) or 0
    new_week=db.scalar(select(func.count()).select_from(Lead).where(base,Lead.created_at>=week)) or 0
    dates={str(d):0 for d in (start.date()+timedelta(days=i) for i in range((end.date()-start.date()).days+1))}
    for d,n in db.execute(select(func.date(Lead.created_at),func.count()).where(base,Lead.created_at>=start,Lead.created_at<=end).group_by(func.date(Lead.created_at))): dates[str(d)]=n
    sources=db.execute(select(LeadSource.name,func.count(Lead.id)).select_from(Lead).join(LeadSource,Lead.source_id==LeadSource.id,isouter=True).where(base,Lead.created_at>=start,Lead.created_at<=end).group_by(LeadSource.name)).all()
    cutoff=today-timedelta(hours=24)
    attention=db.scalars(select(Lead).where(base,Lead.status==LeadStatus.new,Lead.score>=80,Lead.created_at<cutoff,~Lead.id.in_(select(LeadEvent.lead_id).where(LeadEvent.event_type=="contacted"))).limit(10)).all()
    appointments=db.scalars(select(Appointment).join(Lead).where(base,Appointment.status!="cancelled",Appointment.starts_at>=today.replace(hour=0,minute=0,second=0,microsecond=0),Appointment.starts_at<today.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1))).all()
    return {"totals":{"total_leads":total,"hot_leads":hot,"new_this_week":new_week,"qualified":funnel["qualified"],"booked":funnel["booked"],"won":funnel["won"],"lost":funnel["lost"]},"conversion_rate":round(funnel["won"] / total * 100,1) if total else 0,"leads_per_day":[{"date":d,"count":n} for d,n in dates.items()],"leads_by_source":[{"source":n or "Unknown","count":c} for n,c in sources],"funnel":[{"status":s,"count":funnel[s]} for s in STATUSES],"needs_attention":[{"id":x.id,"name":x.name,"score":x.score} for x in attention],"todays_appointments":[{"id":x.id,"lead_id":x.lead_id,"starts_at":x.starts_at} for x in appointments]}
@router.get("/weekly")
def weekly(week_start:date|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
    now=datetime.now(timezone.utc);monday=week_start or (now.date()-timedelta(days=now.weekday()));start=datetime.combine(monday,datetime.min.time(),timezone.utc);end=start+timedelta(days=7);base=[Lead.team_id==user.team_id,Lead.created_at>=start,Lead.created_at<end]
    total=db.scalar(select(func.count()).select_from(Lead).where(*base)) or 0; booked=db.scalar(select(func.count()).select_from(Lead).where(*base,Lead.status.in_([LeadStatus.booked,LeadStatus.won]))) or 0
    sources=db.execute(select(LeadSource.name,func.count(Lead.id)).select_from(Lead).join(LeadSource,Lead.source_id==LeadSource.id,isouter=True).where(*base).group_by(LeadSource.name)).all()
    stages=db.execute(select(Lead.status,func.count()).where(*base).group_by(Lead.status)).all()
    first=db.execute(select(Lead.created_at,func.min(LeadEvent.created_at)).join(LeadEvent,LeadEvent.lead_id==Lead.id).where(*base,LeadEvent.event_type=="contacted").group_by(Lead.id)).all();avg=round(sum((b-a).total_seconds()/60 for a,b in first)/len(first),1) if first else None
    previous=[Lead.team_id==user.team_id,Lead.created_at>=start-timedelta(days=7),Lead.created_at<start];prev=db.scalar(select(func.count()).select_from(Lead).where(*previous)) or 0
    prev_booked=db.scalar(select(func.count()).select_from(Lead).where(*previous,Lead.status.in_([LeadStatus.booked,LeadStatus.won]))) or 0
    prev_first=db.execute(select(Lead.created_at,func.min(LeadEvent.created_at)).join(LeadEvent,LeadEvent.lead_id==Lead.id).where(*previous,LeadEvent.event_type=="contacted").group_by(Lead.id)).all()
    prev_avg=round(sum((b-a).total_seconds()/60 for a,b in prev_first)/len(prev_first),1) if prev_first else None
    rate=round(booked/total*100,1) if total else 0;prev_rate=round(prev_booked/prev*100,1) if prev else None
    def change(current, previous):
        if previous is None:return {"absolute":None,"percent":None}
        return {"absolute":round(current-previous,1),"percent":round((current-previous)/previous*100,1) if previous else None}
    return {"leads_per_source":[{"source":n or "Unknown","count":c} for n,c in sources],"avg_first_response_minutes":avg,"conversion_by_stage":[{"status":str(s.value if hasattr(s,'value') else s),"share":round(c/total*100,1) if total else 0} for s,c in stages],"booking_rate":rate,"change_vs_previous_week":{"total_leads":change(total,prev) if prev else {"absolute":None,"percent":None},"booking_rate":change(rate,prev_rate),"avg_response_time":change(avg,prev_avg) if avg is not None else {"absolute":None,"percent":None}}}
