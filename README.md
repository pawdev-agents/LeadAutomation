# Lead Automation MVP

Run locally:

```powershell
Copy-Item .env.example .env
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

For Docker, use `docker compose up --build`. The development bootstrap endpoint returns a demo team ID and bearer token: `POST /api/dev/bootstrap`.

Public capture: `POST /public/{team_id}/capture`; webhook capture: `POST /webhooks/{team_id}/{source}`. Pass a `website` field only as a hidden honeypot field. API docs are at `/docs`.
