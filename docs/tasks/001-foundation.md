# Active task: service foundation

Build the initial FastAPI service foundation for the Usage Metering and Billing Engine. Start with configuration, a PostgreSQL connection, Alembic, a health endpoint, and test infrastructure. Do not implement Stripe payment mutations until webhook verification and idempotent event persistence have a documented design and tests.

Acceptance criteria:

- The API and PostgreSQL start with Docker Compose.
- Configuration loads from environment variables without exposing secrets.
- The health endpoint returns a successful response.
- Linting, type checks, and tests pass in local and CI environments.
