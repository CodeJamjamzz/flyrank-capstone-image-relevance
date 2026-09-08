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
| Import a complete image corpus manifest | `python -m app.cli.import_corpus` |
| Start the paced image-processing worker in the background | `docker compose up -d --build --force-recreate image-worker` |
| Check image-processing status counts | `docker compose exec postgres psql -U metering -d metering -c "SELECT processing_status, count(*) FROM images GROUP BY processing_status;"` |
| List permanent image-processing failures and their recorded errors | `python -m app.cli.failed_images` |
| Requeue failed corpus images after fixing a provider or configuration issue | `python -m app.cli.retry_failed_images` |
| Show recorded vision calls and estimated costs | `python -m app.cli.vision_costs` |
| Check the configured per-tenant AI cost budget | `Get-Content .env | Select-String AI_COST_BUDGET_USD` |
| Create missing embeddings for accepted corpus images | `python -m app.cli.embed_corpus` |
| Show recorded embedding calls and estimated costs | `python -m app.cli.embedding_costs` |
| Create an image-recommendation post | `Invoke-RestMethod -Method Post -Uri http://localhost:8000/posts -ContentType 'application/json' -Body '{"text":"A red fox in a snowy forest"}'` |
| Retrieve post image suggestions | `Invoke-RestMethod http://localhost:8000/posts/<post-id>/images` |
| List pending review suggestions | `Invoke-RestMethod http://localhost:8000/suggestions?status=pending_review` |
| Inspect a suggestion and its machine explanation | `Invoke-RestMethod http://localhost:8000/suggestions/<suggestion-id>` |
| Record a review decision | `Invoke-RestMethod -Method Post -Uri http://localhost:8000/suggestions/<suggestion-id>/review -ContentType 'application/json' -Body '{"decision":"approved","reviewer_note":"Relevant image."}'` |
| Run the 10-case top-1 precision evaluation | `python -m app.cli.evaluate_matching` |
| Stop the image-processing worker | `docker compose stop image-worker` |
| Forward Stripe test events | `stripe listen --forward-to localhost:8000/webhooks/stripe` |
| Trigger a Stripe test event | `stripe trigger customer.subscription.created` |

Copy `.env.example` to `.env` before starting Docker. Set `GEMINI_API_KEY`, `GEMINI_VISION_MODEL`, and `EMBEDDING_MODEL` before starting `image-worker`; the corpus importer refuses a missing or incomplete provenance manifest. Set `STRIPE_WEBHOOK_SECRET` to the signing secret reported by `stripe listen`.
