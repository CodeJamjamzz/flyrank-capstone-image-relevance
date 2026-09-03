# AI image recommendation requirements

## Completion contract

The capability is complete only when every item in this document has a checked item and a corresponding proof in `EVIDENCE.md`. Each implementation must produce structured model output that passes schema validation. Invalid model output is never trusted, and low-confidence classifications are flagged instead of accepted.

## Functional requirements

- [ ] Images are processed by a retryable batch background job.
- [ ] Every vision response validates against a defined schema. Invalid responses retry or enter a flagged state with an explanation.
- [ ] Low-confidence image classifications enter review and do not become accepted metadata automatically.
- [ ] Vision and embedding model usage and cost are tracked for every call.
- [ ] Images store metadata, tags, and embeddings; posts store embeddings.
- [ ] A post returns ranked image suggestions using semantic similarity.
- [ ] Equivalent concepts match semantically, such as "red fox" and "Vulpes vulpes".
- [ ] The mismatch guard rejects an incorrect recommendation, including the wolf-on-a-fox-post scenario, with a human-readable explanation.
- [ ] If no candidate clears the configured threshold, the system returns "no confident match" with reasons.
- [ ] Database models exist for images, tags, embeddings, posts, suggestions, and approval or rejection decisions, with required indexes.
- [ ] API endpoints validate requests and support the review workflow: inspect why, approve, and reject.
- [ ] A labeled evaluation dataset measures top-1 precision, and the measured number appears in `README.md`.

## Scope boundary

Do not build a large image platform or a customer-facing frontend. The corpus contains at least 40 images in at least four categories. A suitable initial animal corpus includes red fox, wolf, dog, bear, and deer. Keep the corpus small enough to inspect manually and process within free-tier limits.

The review interface may be API endpoints, a simple admin table, or a minimal internal page. A separate frontend application is out of scope. Create an evaluation set with at least 10 posts and a labeled correct image for each post. Add cases gradually as failure modes are discovered.

One vision model and one embedding model are sufficient. Model comparison is optional and is not a core requirement.

## Model, corpus, and validation rules

Use Gemini Flash's free tier without a credit card or fully local Ollama models. Process images in batches, retain per-call usage and cost records, and keep each run visible and inexpensive.

Use only licensed-free images, such as Unsplash or Pexels assets. Document license links for every corpus source. Commit the small corpus or provide a deterministic download script so evaluators can reproduce the project.

Define a Pydantic schema for vision output before integrating a model. Store the raw response only when necessary for debugging and ensure it contains no secrets. Validate the response before persistence. Record invalid, retried, and rejected outcomes explicitly.
