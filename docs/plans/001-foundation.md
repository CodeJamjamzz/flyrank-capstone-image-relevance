# Foundation plan

1. Establish configuration, database session management, and Alembic migrations.
2. Define customer, subscription, usage event, quota, invoice, and processed-webhook-event models with required unique constraints.
3. Implement idempotent usage ingestion and transactional quota evaluation.
4. Implement billing calculation services using `Decimal` and tested period boundaries.
5. Integrate Stripe Test Mode subscriptions and verified, idempotent webhook handling.
6. Add API, domain, and database integration tests for expected and duplicate-event paths.
