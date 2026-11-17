"""Create demo data. Safe to run twice: does nothing if the demo team already exists."""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Appointment, Lead, LeadEvent, LeadSource, LeadStatus, Team, User
from app.services.leads import score

TEAM_NAME = "Demo Studio"
PASSWORD = "demo12345"
USERS = [
    ("admin@demo-team.com", "Admin Demo", "admin"),
    ("sara@demo-team.com", "Sara Khan", "member"),
    ("omar@demo-team.com", "Omar Ali", "member"),
]
SOURCES = [("website", "form"), ("google", "ads"), ("referral", "referral")]
UTM = {
    "website": {},
    "google": {"source": "google", "medium": "cpc", "campaign": "spring-sale"},
    "referral": {"source": "referral"},
}
FIRST = ["Ayesha", "Omar", "Hina", "Bilal", "Zara", "Usman", "Maryam", "Daniyal",
         "Sana", "Hamza", "Laiba", "Faisal", "Noor", "Imran", "Mehwish", "Talha"]
LAST = ["Khan", "Farooq", "Malik", "Ahmed", "Raza", "Sheikh", "Qureshi", "Siddiqui", "Butt", "Iqbal"]
SERVICES = [None, "Web design", "SEO", "Branding", "Consulting"]
STATUS_MIX = (["new"] * 10 + ["contacted"] * 9 + ["qualified"] * 7
              + ["booked"] * 6 + ["won"] * 5 + ["lost"] * 3)


def show(team_id):
    print("Demo team id:", team_id)
    print("Login: admin@demo-team.com / " + PASSWORD)
    print("Public capture URL: http://localhost:8000/public/%s/capture" % team_id)


def main():
    Base.metadata.create_all(engine)
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        team = db.scalar(select(Team).where(Team.name == TEAM_NAME))
        if team:
            print("Demo data already exists, nothing changed.")
            show(team.id)
            return

        team = Team(name=TEAM_NAME, timezone="Asia/Karachi")
        db.add(team)
        db.flush()
        users = [
            User(team_id=team.id, email=e, name=n, role=r, password_hash=hash_password(PASSWORD))
            for e, n, r in USERS
        ]
        db.add_all(users)
        sources = {}
        for name, kind in SOURCES:
            src = LeadSource(team_id=team.id, name=name, source_type=kind)
            db.add(src)
            sources[name] = src
        db.flush()

        statuses = STATUS_MIX[:]
        rng.shuffle(statuses)
        counts = {}
        for i, status in enumerate(statuses):
            first, last = rng.choice(FIRST), rng.choice(LAST)
            source_name = rng.choices(list(sources), weights=[5, 3, 2])[0]
            budget = rng.choice([None, 1000, 3000, 5000, 8000, 15000])
            urgency = rng.choice([None, "low", "medium", "high", "urgent"])
            service = rng.choice(SERVICES)
            created = now - timedelta(days=rng.randint(0, 44), hours=rng.randint(0, 23),
                                      minutes=rng.randint(0, 59))
            lead = Lead(
                team_id=team.id,
                source_id=sources[source_name].id,
                owner_id=users[i % len(users)].id,
                name="%s %s" % (first, last),
                email=("%s.%s%d@clientmail.com" % (first, last, i)).lower(),
                phone="+92300%07d" % rng.randint(1000000, 9999999),
                status=LeadStatus(status),
                score=score(SimpleNamespace(budget=budget, urgency=urgency,
                                            source=source_name, service_type=service)),
                service_type=service,
                budget=budget,
                urgency=urgency,
                utm=UTM[source_name],
                created_at=created,
                updated_at=created,
            )
            db.add(lead)
            db.flush()
            db.add(LeadEvent(lead_id=lead.id, event_type="lead_created", created_at=created,
                             payload={"source": source_name, "score": lead.score}))

            if status != "new":
                contacted_at = min(created + timedelta(minutes=rng.randint(10, 600)), now)
                lead.last_contacted_at = contacted_at
                db.add(LeadEvent(lead_id=lead.id, event_type="contacted", created_at=contacted_at))
                if status in ("qualified", "booked", "won") and rng.random() < 0.6:
                    lead.replied_at = min(contacted_at + timedelta(hours=1), now)

            if status == "booked":
                starts = now + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 8))
                db.add(Appointment(lead_id=lead.id, starts_at=starts,
                                   ends_at=starts + timedelta(hours=1), status="scheduled"))
            elif status == "won":
                starts = min(created + timedelta(days=2), now - timedelta(days=1))
                db.add(Appointment(lead_id=lead.id, starts_at=starts,
                                   ends_at=starts + timedelta(hours=1), status="completed"))
            counts[status] = counts.get(status, 0) + 1

        db.commit()
        print("Created demo team, %d users, %d sources, %d leads: %s"
              % (len(users), len(sources), len(statuses), counts))
        show(team.id)


if __name__ == "__main__":
    main()
