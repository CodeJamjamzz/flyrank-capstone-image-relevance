# Usage Metering and Billing Engine

## Project context

This service provides SaaS applications with durable usage metering, subscription quota enforcement, accurate billing calculations, idempotent usage ingestion, and Stripe Test Mode subscription and webhook integration.

It also includes an AI-assisted image recommendation capability. It processes a small, licensed image corpus, extracts validated image metadata, creates image and post embeddings, ranks image suggestions for posts, and routes uncertain or mismatched results to human review.

## Tech stack

- Python 3.12 and FastAPI
- PostgreSQL 16
- SQLAlchemy and Alembic for persistence and migrations
- Stripe Python SDK and Stripe CLI for Test Mode webhook testing
- Gemini Flash free tier or local Ollama models for vision and embeddings
- PostgreSQL vector storage for image and post embeddings
- Docker Compose for local development
- Pytest, Ruff, and mypy for quality checks

## Engineering rules

- Keep the capstone in its own public GitHub repository. Do not combine it with unrelated work.
- Use only free-tier tools and services. Do not require a credit card for development, demonstrations, or evaluation.
- Record material AI assistance in `BUILDLOG.md`, including what AI helped with, corrections made, and the final reasoning. Be prepared to explain any selected code.
- Validate every vision-model response against a Pydantic schema. Retry or flag invalid output; never accept it silently.
- Track vision and embedding cost or usage per model call. Use batch jobs with retries for image processing.
- Keep the labeled image corpus small, licensed for free use, and reproducible through committed assets or a documented download script.
- Flag low-confidence classifications for review. A recommendation must include a human-readable rejection reason when the mismatch guard rejects it or no image clears the confidence threshold.
- Use `Decimal` for money and quantity calculations that affect billing. Never use binary floating-point values for currency.
- Store timestamps in UTC and make time-window boundaries explicit.
- Protect usage ingestion with an idempotency key and a database uniqueness constraint scoped to the customer and event source.
- Verify Stripe webhook signatures against the unmodified request body before processing an event. Treat Stripe event IDs as idempotency keys.
- Do not log, commit, or expose API keys, webhook secrets, or customer payment data.
- Make schema changes through reviewed Alembic migrations only.
- Keep request handlers thin. Put metering, quota, and billing rules in focused domain services with unit tests.
- Add or update tests for every behavior change. Preserve existing comments unless the task requires changing them.
- Do not introduce `Any` or weaken static typing to bypass an error.

## Workflow

Before writing code, read the active task brief in `docs/tasks/`, then consult the matching plan in `docs/plans/` and the project commands in `docs/ai/commands.md`.
