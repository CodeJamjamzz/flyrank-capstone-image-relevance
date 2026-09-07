# Evidence checklist

This file provides reviewer-verifiable proof for the AI image recommendation completion contract. Do not mark an item complete until the evidence includes a command, test output, API response, screenshot reference, or committed artifact that a reviewer can inspect quickly.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Retryable batch image processing | Implemented | `tests/unit/test_image_processing_worker.py` verifies retry behavior. Corpus completion remains an operational task because some live images are still failed. |
| Schema validation and invalid-output handling | Verified | `tests/unit/test_image_metadata_schemas.py` validates accepted payloads and rejects malformed, duplicate, unknown-field, and unsupported-version responses. |
| Low-confidence classification flagging | Verified | `tests/unit/test_image_metadata_schemas.py` verifies confidence validation and the low-confidence processing path. |
| Per-call vision and embedding cost tracking | Verified | Live commands `python -m app.cli.vision_costs` and `python -m app.cli.embedding_costs` report recorded model calls, units, status, and estimated cost. |
| Image and post embedding storage | Verified | Live evaluation on 2026-09-07 created post embeddings and used accepted image embeddings; see `data/evaluation/evaluation-report.json`. |
| Ranked post image suggestions | Verified | Live evaluation report records the top-ranked passing suggestion for all 10 cases. |
| Equivalent-concept semantic match | Verified | Stage 3 taxonomy tests cover `Vulpes vulpes` matching the red-fox canonical subject. |
| Wolf-on-a-fox-post mismatch rejection | Verified | The live report for `red_fox_snowy_rock` records rejected wolf candidates with a human-readable subject mismatch explanation. |
| No-confident-match response with reasons | Verified | Matching service tests cover unavailable and below-threshold corpus responses with explanations. |
| Database models and indexes | Verified | `alembic upgrade head` applied migration `20260907_0002`; migration tests verify the global pending-review index. |
| Validated API and review workflow | Verified | `tests/features/test_review_api.py` covers pending listing, inspection, approval, rejection, invalid input, unknown IDs, and review conflicts. |
| Labeled evaluation set and top-1 precision | Verified | Live command `python -m app.cli.evaluate_matching` on 2026-09-07 produced `correct_top_1=9/10`, `top_1_precision=0.9000`, saved in `data/evaluation/evaluation-report.json`. |