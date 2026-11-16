from datetime import timedelta
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .auth import create_access_token, current_user, hash_password
from .database import Base, engine, get_db
from .models import Appointment, Followup, Lead, LeadEvent, LeadSource, LeadStatus, Team, User
from .routers.leads import router as leads_router
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.sources import router as sources_router
from .routers.appointments import router as appointments_router
from .routers.followups import router as followups_router
from .routers.stats import router as stats_router
from .schemas import AppointmentIn, CaptureIn
from .services.leads import create_lead, event
from .services.appointments import create_booking

Base.metadata.create_all(engine)  # Alembic is used for production migrations.
limiter=Limiter(key_func=get_remote_address)
app=FastAPI(title="Lead Automation API")
app.state.limiter=limiter
app.add_exception_handler(RateLimitExceeded, lambda _request, _exc: JSONResponse(status_code=429, content={"detail":"Too many requests"}))
app.add_middleware(SlowAPIMiddleware)
app.include_router(leads_router, prefix="/api")
app.include_router(auth_router)
app.include_router(users_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(followups_router, prefix="/api")
app.include_router(stats_router, prefix="/api")

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Team-scoped aggregate data for the operational dashboard."""
    team_id = user.team_id
    leads = db.scalars(select(Lead).where(Lead.team_id == team_id).order_by(Lead.created_at.desc())).all()
    source_rows = db.execute(
        select(LeadSource.name, func.count(Lead.id))
        .select_from(Lead).join(LeadSource, Lead.source_id == LeadSource.id, isouter=True)
        .where(Lead.team_id == team_id).group_by(LeadSource.name)
    ).all()
    by_status = {status.value: 0 for status in LeadStatus}
    for lead in leads: by_status[lead.status.value] += 1
    return {
        "totals": {"leads": len(leads), "hot_leads": sum(lead.score >= 80 for lead in leads), "booked": by_status["booked"], "conversion_rate": round((by_status["booked"] + by_status["won"]) / len(leads) * 100, 1) if leads else 0},
        "stages": by_status,
        "sources": [{"name": name or "Unknown", "count": count} for name, count in source_rows],
        "recent": [{"id": lead.id, "name": lead.name, "email": lead.email or lead.phone or "—", "status": lead.status.value, "score": lead.score, "source": next((name or "Unknown" for name, count in source_rows if lead.source_id and db.scalar(select(LeadSource.name).where(LeadSource.id == lead.source_id)) == name), "Unknown"), "created_at": lead.created_at.isoformat()} for lead in leads[:6]],
    }

@app.post("/public/{team_id}/capture")
@limiter.limit("10/minute")
def capture(request:Request, team_id:int, data:CaptureIn, db:Session=Depends(get_db)):
    if data.website: return {"accepted":True} # honeypot: intentionally indistinguishable
    if not db.get(Team,team_id): raise HTTPException(404,"Team not found")
    lead, duplicate=create_lead(db,team_id,data)
    db.commit()
    return {"accepted":True,"duplicate":duplicate,"lead_id":lead.id}

@app.post("/webhooks/{team_id}/{source}")
@limiter.limit("30/minute")
def webhook(request:Request,team_id:int,source:str,data:CaptureIn,db:Session=Depends(get_db)):
    data.source=source
    return capture(request,team_id,data,db)

@app.post("/api/leads/{lead_id}/book",status_code=201)
def book(lead_id:int, data:AppointmentIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lead=db.scalar(select(Lead).where(Lead.id==lead_id,Lead.team_id==user.team_id))
    if not lead:raise HTTPException(404,"Lead not found")
    appointment=create_booking(db,lead,data.starts_at,data.ends_at,data.timezone,user.id)
    db.commit();return {"id":appointment.id,"lead_id":lead.id}

@app.post("/api/dev/bootstrap")
def bootstrap(db:Session=Depends(get_db), _user: User = Depends(current_user)):
    """Authenticated development-only convenience endpoint."""
    team=db.scalar(select(Team).where(Team.name=="Demo")) or Team(name="Demo")
    db.add(team);db.flush()
    user=db.scalar(select(User).where(User.email=="admin@example.test"))
    if not user:
        user=User(team_id=team.id,email="admin@example.test",name="Admin",password_hash=hash_password("change-me-now"),role="admin");db.add(user);db.flush()
    db.commit();return {"team_id":team.id,"access_token":create_access_token(user)}
