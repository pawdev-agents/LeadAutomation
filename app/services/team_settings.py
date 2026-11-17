import copy

DEFAULTS = {
    "scoring_weights": {},
    "followup_delays_days": [1, 3, 7],
    "auto_reply_subject": "Thanks for getting in touch",
    "auto_reply_body": "Hi {name}, thanks for your enquiry. We will contact you shortly.",
    "working_hours": {"start": "09:00", "end": "17:00", "days": [0, 1, 2, 3, 4]},
}


def merged(team) -> dict:
    """Team settings with defaults filled in for anything not saved yet."""
    data = copy.deepcopy(DEFAULTS)
    data.update(copy.deepcopy(team.settings or {}))
    return data
