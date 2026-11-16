from app.models import LeadStatus
from app.routers.leads import ALLOWED_TRANSITIONS
from app.services.leads import score

def test_status_transition_rules():
    assert LeadStatus.booked in ALLOWED_TRANSITIONS[LeadStatus.qualified]
    assert LeadStatus.new not in ALLOWED_TRANSITIONS[LeadStatus.booked]

def test_hot_lead_scoring():
    lead=type("LeadInput",(),{"budget":8000,"urgency":"urgent","source":"referral","service_type":"consulting"})()
    assert score(lead) >= 80
