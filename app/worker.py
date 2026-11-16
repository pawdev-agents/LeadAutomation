"""Polling worker. Replace `deliver_email` with a provider adapter when mail is connected."""
import logging, time
from datetime import datetime, timezone
from sqlalchemy import select
from .database import SessionLocal
from .models import Followup, Lead, LeadEvent, LeadStatus
logging.basicConfig(level=logging.INFO)

def deliver_email(lead, kind):
    logging.info("email queued: lead=%s kind=%s recipient=%s", lead.id, kind, lead.email)

def tick():
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        jobs=db.scalars(select(Followup).where(Followup.scheduled_for<=now,Followup.sent_at.is_(None),Followup.cancelled_at.is_(None))).all()
        for job in jobs:
            lead=db.get(Lead,job.lead_id)
            stop_sequence=job.kind.startswith("followup_") and (lead.replied_at or lead.status in (LeadStatus.booked,LeadStatus.won,LeadStatus.lost))
            if stop_sequence:
                job.cancelled_at=now; continue
            # Marking after provider success preserves at-least-once delivery; key prevents duplicate provider sends.
            deliver_email(lead,job.kind); job.sent_at=now
            if job.kind in ("auto_reply","followup_day_1","followup_day_3","followup_day_7"): lead.last_contacted_at=now
            db.add(LeadEvent(lead_id=lead.id,event_type="followup_sent",payload={"kind":job.kind,"channel":job.channel}))
        db.commit()
if __name__=="__main__":
    while True:
        tick();time.sleep(30)
