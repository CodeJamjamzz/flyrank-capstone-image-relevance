# Usage Metering and Billing Engine

The Usage Metering and Billing Engine is a backend service for SaaS applications that need reliable, auditable usage-based billing. It records customer usage, enforces subscription quotas, calculates billing costs accurately, and prevents duplicate usage records through idempotency keys.

The service integrates with Stripe Test Mode to manage subscriptions and process Stripe webhooks securely. PostgreSQL provides durable storage for customers, subscriptions, usage records, quota state, invoices, and processed external events. FastAPI exposes the service API, while Docker Compose provides a repeatable local environment.

Alongside the billing workflow, the capstone includes an AI-assisted semantic image recommendation capability. A batch worker analyzes a small, licensed image corpus, validates structured vision output, generates embeddings for images and posts, and returns ranked image suggestions. A mismatch guard and human review workflow keep low-confidence or incorrect recommendations from being accepted automatically.

## Core capabilities

- Accept and store customer usage events with durable idempotency guarantees.
- Evaluate subscription quotas without allowing duplicate events or concurrent requests to over-count usage.
- Calculate billable usage and monetary amounts with `Decimal` and explicit billing-period boundaries.
- Synchronize subscription lifecycle events through verified, idempotent Stripe webhooks.
- Process images in retryable background batches and store validated captions, tags, classifications, embeddings, model usage, and cost records.
- Return ranked image recommendations for posts using semantic similarity, including equivalent concepts such as "red fox" and "Vulpes vulpes".
- Reject mismatched, low-confidence, or insufficiently similar recommendations with clear explanations and a review workflow.
- Provide reproducible local development and evaluation through documented commands, Docker Compose, and a small committed corpus or download script when AI evaluation is used.

## Non-negotiable reliability requirements

- PostgreSQL is the source of truth for billing-related state.
- Money and billing quantities never use binary floating-point arithmetic.
- Usage-event idempotency is enforced in the database, not only in application memory.
- Stripe webhook signatures are verified against the unmodified request body before any side effect occurs.
- Duplicate Stripe event deliveries are safely acknowledged without repeating state changes.
- Secrets stay in `.env` files and never enter source code, logs, or commits.
