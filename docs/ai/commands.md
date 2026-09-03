# Project commands

Run commands from the repository root. If a command fails, first inspect this file, then verify the active task brief and local environment variables before changing code.

| Purpose | Command |
| --- | --- |
| Create a local environment | `python -m venv .venv` |
| Activate it in PowerShell | `.\\.venv\\Scripts\\Activate.ps1` |
| Install application and development dependencies | `python -m pip install -e ".[dev]"` |
| Start API and PostgreSQL with Docker | `docker compose up --build` |
| Stop local containers | `docker compose down` |
| Run the API outside Docker | `uvicorn app.main:app --reload` |
| Run linting | `ruff check app tests` |
| Format checks | `ruff format --check app tests` |
| Run type checks | `mypy app` |
| Run tests | `pytest` |
| Create a migration | `alembic revision --autogenerate -m "describe_change"` |
| Apply migrations | `alembic upgrade head` |
| Forward Stripe test events | `stripe listen --forward-to localhost:8000/webhooks/stripe` |
| Trigger a Stripe test event | `stripe trigger customer.subscription.created` |

Copy `.env.example` to `.env` before starting Docker. Set `STRIPE_WEBHOOK_SECRET` to the signing secret reported by `stripe listen`.
