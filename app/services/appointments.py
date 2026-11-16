from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Appointment, Followup, LeadStatus
from .leads import event

def create_booking(db, lead, starts_at, ends_at, timezone, actor_id):
    if ends_at <= starts_at: raise HTTPException(422,"ends_at must be after starts_at")
    if db.scalar(select(Appointment).where(Appointment.lead_id==lead.id)): raise HTTPException(409,"Lead already has an appointment")
    appointment=Appointment(lead_id=lead.id,starts_at=starts_at,ends_at=ends_at,timezone=timezone)
    lead.status=LeadStatus.booked; event(db,lead.id,"appointment_booked",{"starts_at":starts_at.isoformat()},actor_id)
    for hours in (24,1): db.add(Followup(lead_id=lead.id,kind=f"appointment_reminder_{hours}h",scheduled_for=starts_at-timedelta(hours=hours),idempotency_key=f"appointment:{lead.id}:{hours}h"))
    db.add(appointment); return appointment
