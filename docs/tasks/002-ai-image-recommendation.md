# Active task: AI image recommendation foundation

Establish the documented foundation for the AI image recommendation capability before implementation. Follow `docs/specs/ai-image-recommendation-requirements.md`, preserve the billing engine's reliability rules, and do not mark an evidence item complete without verifiable output.

Acceptance criteria:

- The data model and index design are documented before migrations are written.
- The vision-output schema, confidence policy, and mismatch-guard behavior are specified before model calls are integrated.
- The corpus plan identifies free licensed sources and a reproducible acquisition method.
- The evaluation plan includes at least 10 labeled posts and records the wolf-on-a-fox-post rejection case.
- `EVIDENCE.md` is the source of proof for the completion contract.
