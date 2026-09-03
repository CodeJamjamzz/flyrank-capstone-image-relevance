# AI image recommendation plan

1. Define database models for images, tags, embeddings, posts, suggestions, review decisions, model calls, and batch-job attempts. Add indexes for lookup, similarity retrieval, and pending review work.
2. Define the versioned Pydantic schema for vision metadata and rules for invalid, low-confidence, and retryable responses.
3. Create a reproducible corpus of at least 40 licensed-free images across at least four categories, with source and license records.
4. Implement the retryable batch image-processing job, structured vision validation, image embedding generation, and per-call cost tracking.
5. Implement post embedding generation, semantic ranking, mismatch-guard rules, and the explicit "no confident match" response.
6. Add review endpoints for listing suggestions, inspecting a decision explanation, approving, and rejecting.
7. Create at least 10 labeled post-to-image evaluation cases, measure top-1 precision, add the result to `README.md`, and paste proof for each completion item into `EVIDENCE.md`.
