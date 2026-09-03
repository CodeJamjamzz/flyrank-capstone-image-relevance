# Architecture overview

The API receives authenticated usage events, Stripe webhooks, images, posts, and review decisions. PostgreSQL is the source of truth for billing-related state and image-recommendation records. Domain services calculate billing amounts using `Decimal`; request handlers orchestrate validation and responses only.

Usage writes must be atomic and reject a duplicate idempotency key for the same customer and source. Stripe webhook processing must verify the signature from the raw body, persist the Stripe event ID transactionally, and safely acknowledge repeated deliveries without repeating side effects.

## AI image recommendation flow

```mermaid
flowchart TD
    A[Licensed image corpus] --> B[Batch background job with retries]
    B --> C[Vision model]
    C --> D{Schema validation and confidence check}
    D -->|Invalid or low confidence| E[Flag for review with reason]
    D -->|Valid| F[Image metadata: tags, caption, confidence]
    F --> G[Embed image caption]
    G --> H[(Image embeddings)]
    I[Post text] --> J[Embed post text]
    J --> K[(Post embeddings)]
    H --> L[Similarity ranking]
    K --> L
    L --> M[Mismatch guard: tags, threshold, confidence]
    M -->|Pass| N[Ranked image suggestion]
    M -->|Fail| O[No confident match or rejection reason]
    N --> P[Review API: approve or reject]
    O --> P
```

The two embedding streams meet only at similarity ranking. Every recommendation passes the mismatch guard before a human sees it. The guard considers semantic similarity, image tags, vision confidence, and configured thresholds. It rejects an obviously incorrect recommendation, such as a wolf image suggested for a red-fox post, and records a human-readable explanation.
