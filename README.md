# LeadAutomation

LeadAutomation is a small team lead-management app: capture inbound leads, qualify them through a pipeline, schedule appointments, automate follow-ups, and review weekly results.

## Architecture

- `app/` is a FastAPI API backed by SQLite and SQLAlchemy.
- `app/worker.py` polls due follow-ups and logs email delivery work.
- `frontend/` is a Next.js application using React Query.
- `scripts/seed.py` creates a repeatable demo team and lead data.

## Windows PowerShell setup

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\scripts\seed.py
uvicorn app.main:app --reload
```

Start the worker in another PowerShell window:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

Start the frontend in a third window:

```powershell
Set-Location .\frontend
npm.cmd install
npm.cmd run dev
```

The API is available at `http://127.0.0.1:8000`; the frontend is available at `http://localhost:3000`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | Required signing secret for API access tokens. Use a long random value outside local development. |
| `DATABASE_URL` | SQLAlchemy URL, normally `sqlite:///./data/leads.db`. |
| `PUBLIC_BASE_URL` | Public API base URL used in external URLs. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. |
| `ENABLE_DEV_BOOTSTRAP` | Enables the development bootstrap API only when `true`. |
| `NEXT_PUBLIC_API_URL` | Browser-visible URL of the API used by Next.js. |

## Demo login

- Admin: `admin@demo-team.com` / `demo12345`
- Member: `sara@demo-team.com` / `demo12345`

## Checks

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q

Set-Location .\frontend
npm.cmd run lint
npm.cmd run build
```

## Known limitations

- SQLite is appropriate for local development and small deployments, not high-concurrency production use.
- The worker logs follow-up delivery; it does not integrate with an email provider.
- Public capture is rate-limited but should be placed behind TLS and production monitoring.
