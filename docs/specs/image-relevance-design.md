# Image Relevance Design

## Purpose

This document is the implementation contract for the AI image recommendation capability. It defines the model-output schema, matching and mismatch-guard behavior, and PostgreSQL data design. The numeric thresholds are initial configuration values that must be evaluated against the labeled evaluation set before being changed.

## Image metadata contract

The vision model returns JSON only. The application validates it with a versioned Pydantic schema before saving accepted metadata.

```json
{
  "schema_version": 1,
  "caption": "A red fox standing in a snowy forest.",
  "primary_subject": {
    "label": "red fox",
    "scientific_name": "Vulpes vulpes",
    "confidence": 0.96
  },
  "tags": [
    {"label": "red fox", "confidence": 0.98},
    {"label": "snow", "confidence": 0.93},
    {"label": "wildlife", "confidence": 0.91}
  ],
  "overall_confidence": 0.95
}
```

| Field | Rule |
| --- | --- |
| `schema_version` | Must equal `1`. |
| `caption` | Required, 1 to 500 characters. |
| `primary_subject.label` | Required and normalized to lowercase text. |
| `primary_subject.scientific_name` | Optional. |
| `tags` | One to ten unique normalized labels. |
| Confidence values | Numbers from `0.0` through `1.0`. |

Invalid JSON, a missing field, an invalid confidence, or duplicate tags are never accepted. The attempt becomes retryable or failed with an explanation. Metadata with `overall_confidence` below `0.70` is stored as `needs_review`, not used for automatic suggestions.

The image embedding input is the caption followed by the unique tag labels. This makes the embedding represent both description and detected concepts.

## Matching strategy and mismatch guard

1. Generate an embedding for each accepted image metadata record.
2. Generate an embedding for each post text.
3. Rank images by cosine similarity to the post embedding.
4. Run each ranked image through the mismatch guard before returning it.

| Setting | Initial value | Rule |
| --- | ---: | --- |
| `minimum_image_confidence` | 0.70 | Lower-confidence images require review. |
| `minimum_similarity_score` | 0.75 | A candidate below this score is rejected. |
| `maximum_suggestions` | 3 | Return at most three passing candidates. |
| `maximum_processing_attempts` | 3 | Stop automatic retries after three failed attempts. |

The initial taxonomy recognizes these equivalent subjects:

| Canonical subject | Accepted aliases |
| --- | --- |
| red fox | red fox, Vulpes vulpes |
| wolf | wolf, gray wolf, Canis lupus |
| dog | dog, domestic dog, Canis familiaris |
| bear | bear |
| deer | deer |

Guard rules:

- Exclude images whose processing status is not `accepted`.
- Exclude images below the confidence threshold.
- If a post contains a recognized subject or alias, reject a candidate with a different recognized primary subject, even if semantic similarity is high.
- Reject candidates below the similarity threshold.
- If no candidate passes, return `no confident match` with the failing reasons.
- Save a machine-readable reason code and human-readable explanation for every rejection.

Required proof case:

```text
Post: "A red fox in a snowy forest"
Candidate: wolf_004.jpg
Result: rejected
Reason: "Rejected because the post requests red fox, while the image primary subject is wolf."
```

## Database design

```text
images 1 --- 0..1 image_metadata
images 1 --- * image_tags * --- 1 tags
images 1 --- * embeddings
posts  1 --- * embeddings
posts  1 --- * suggestions * --- 1 images
suggestions 1 --- * review_decisions
images 1 --- * processing_attempts
images/posts 1 --- * model_calls
```

| Table | Purpose and key fields |
| --- | --- |
| `images` | `id`, `file_path`, `sha256`, `dataset_label`, `source_url`, `license_url`, `processing_status`, `next_retry_at`, `accepted_at`. |
| `image_metadata` | `image_id`, `schema_version`, `caption`, `primary_subject`, `scientific_name`, `overall_confidence`, `raw_response_json`. |
| `tags` | `id`, `normalized_label`. |
| `image_tags` | `image_id`, `tag_id`, `confidence`. |
| `embeddings` | `id`, `image_id` or `post_id`, `model_name`, `model_version`, `content_sha256`, `embedding`. |
| `posts` | `id`, `text`, `created_at`. |
| `suggestions` | `id`, `post_id`, `image_id`, `similarity_score`, `status`, `reason_code`, `reason_text`. |
| `review_decisions` | `id`, `suggestion_id`, `decision`, `reviewer_note`, `created_at`. |
| `processing_attempts` | `id`, `image_id`, `attempt_number`, `status`, `error_code`, `error_message`, `started_at`, `finished_at`, `retry_at`. |
| `model_calls` | `id`, `image_id` or `post_id`, `operation`, `model_name`, `input_units`, `output_units`, `estimated_cost_usd`, `status`, `created_at`. |

Required constraints and indexes:

- Unique: `images.sha256`, `images.file_path`, `tags.normalized_label`, and `image_metadata.image_id`.
- Unique: `(image_id, tag_id)` in `image_tags`.
- Partial B-tree index: `images(processing_status, next_retry_at)` for pending and retryable images.
- B-tree indexes: `suggestions(post_id, status)`, `review_decisions(suggestion_id)`, and `model_calls(created_at)`.
- Use PostgreSQL `pgvector` with a cosine-distance HNSW index on `embeddings.embedding`.

## Dataset and design gate

The local corpus contains 50 JPG images, 10 each for red fox, wolf, dog, bear, and deer, under `data/corpus/raw/`. Before model processing begins, add `data/corpus/manifest.csv` with each image ID, file path, manual label, source URL, and license URL.

The design gate is complete when this document, the 50-image corpus, and the completed manifest are committed. Only then should database migrations, model calls, and batch-job implementation begin.
