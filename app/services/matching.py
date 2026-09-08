from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.orm import Session, aliased

from app.core.config import Settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.db.models import (
    Embedding,
    Image,
    ImageMetadata,
    ImageProcessingStatus,
    Post,
    Suggestion,
    SuggestionStatus,
)
from app.schemas.common import normalize_label
from app.services.embeddings import latest_embedding_for_post

SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "red fox": ("red fox", "vulpes vulpes"),
    "wolf": ("wolf", "gray wolf", "canis lupus"),
    "dog": ("dog", "domestic dog", "canis familiaris"),
    "bear": ("bear",),
    "deer": ("deer",),
}


class PostNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class RankedCandidate:
    image: Image
    metadata: ImageMetadata
    similarity_score: float


def recognize_subject(text: str) -> str | None:
    normalized = normalize_label(text)
    for subject, aliases in SUBJECT_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return subject
    return None


def create_suggestions_if_needed(
    session: Session,
    post_id: uuid.UUID,
    configuration: Settings,
) -> list[Suggestion]:
    existing = list_suggestions(session, post_id)
    if existing:
        return existing

    post = session.get(Post, post_id)
    if post is None:
        raise PostNotFoundError(f"Post {post_id} does not exist")

    post.recognized_subject = recognize_subject(post.text)
    post_embedding = latest_embedding_for_post(session, post.id)
    if post_embedding is None:
        return _persist_no_confident_match(
            session,
            post,
            "post_embedding_unavailable",
            "No confident match: the post embedding is not available yet.",
        )

    candidates = rank_candidates(session, post_embedding, configuration, post.tenant_id)
    if not candidates:
        return _persist_no_confident_match(
            session,
            post,
            "corpus_embedding_unavailable",
            "No confident match: no accepted image embeddings are available "
            "while corpus processing continues.",
        )

    accepted_count = 0
    rejection_reasons: list[str] = []
    for candidate in candidates:
        reason = guard_candidate(post, candidate, configuration)
        if reason is not None:
            reason_code, reason_text = reason
            rejection_reasons.append(reason_text)
            session.add(
                Suggestion(
                    post_id=post.id,
                    image_id=candidate.image.id,
                    similarity_score=Decimal(str(candidate.similarity_score)),
                    status=SuggestionStatus.REJECTED,
                    reason_code=reason_code,
                    reason_text=reason_text,
                )
            )
            continue

        if accepted_count < configuration.maximum_suggestions:
            accepted_count += 1
            session.add(
                Suggestion(
                    post_id=post.id,
                    image_id=candidate.image.id,
                    similarity_score=Decimal(str(candidate.similarity_score)),
                    status=SuggestionStatus.PENDING_REVIEW,
                    reason_code="matched",
                    reason_text="Candidate passed similarity and subject-mismatch checks.",
                )
            )

    if accepted_count == 0:
        session.flush()
        summary = rejection_reasons[0] if rejection_reasons else "No candidate passed the guard."
        session.add(
            Suggestion(
                post_id=post.id,
                status=SuggestionStatus.NO_CONFIDENT_MATCH,
                reason_code="no_confident_match",
                reason_text=f"No confident match: {summary}",
            )
        )
    session.commit()
    return list_suggestions(session, post.id)


def rank_candidates(
    session: Session,
    post_embedding: Embedding,
    configuration: Settings,
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID,
) -> list[RankedCandidate]:
    image_embedding = aliased(Embedding)
    latest_image_embedding_id = (
        select(image_embedding.id)
        .where(image_embedding.image_id == Image.id)
        .order_by(image_embedding.created_at.desc(), image_embedding.id.desc())
        .correlate(Image)
        .limit(1)
        .scalar_subquery()
    )
    distance = image_embedding.embedding.cosine_distance(post_embedding.embedding).label("distance")
    rows = session.execute(
        select(Image, ImageMetadata, distance)
        .join(ImageMetadata, ImageMetadata.image_id == Image.id)
        .join(image_embedding, image_embedding.id == latest_image_embedding_id)
        .where(
            Image.tenant_id == tenant_id,
            Image.processing_status == ImageProcessingStatus.ACCEPTED,
            ImageMetadata.overall_confidence
            >= Decimal(str(configuration.minimum_image_confidence)),
        )
        .order_by(distance, Image.id)
    ).all()
    return [
        RankedCandidate(
            image=image,
            metadata=metadata,
            similarity_score=max(-1.0, min(1.0, 1.0 - float(candidate_distance))),
        )
        for image, metadata, candidate_distance in rows
    ]


def guard_candidate(
    post: Post,
    candidate: RankedCandidate,
    configuration: Settings,
) -> tuple[str, str] | None:
    candidate_subject = recognize_subject(
        " ".join(
            value
            for value in (
                candidate.metadata.primary_subject,
                candidate.metadata.scientific_name,
            )
            if value
        )
    )
    if (
        post.recognized_subject is not None
        and candidate_subject is not None
        and post.recognized_subject != candidate_subject
    ):
        return (
            "subject_mismatch",
            "Rejected because the post requests "
            f"{post.recognized_subject}, while the image primary subject is "
            f"{candidate.metadata.primary_subject}.",
        )
    if candidate.similarity_score < configuration.minimum_similarity_score:
        return (
            "similarity_below_threshold",
            "Rejected because the similarity score "
            f"{candidate.similarity_score:.4f} is below the required "
            f"{configuration.minimum_similarity_score:.2f}.",
        )
    return None


def list_suggestions(session: Session, post_id: uuid.UUID) -> list[Suggestion]:
    return list(
        session.scalars(
            select(Suggestion)
            .where(Suggestion.post_id == post_id)
            .order_by(
                case(
                    (Suggestion.status == SuggestionStatus.PENDING_REVIEW, 0),
                    (Suggestion.status == SuggestionStatus.REJECTED, 1),
                    else_=2,
                ),
                Suggestion.similarity_score.desc().nullslast(),
                Suggestion.id,
            )
        )
    )


def _persist_no_confident_match(
    session: Session,
    post: Post,
    reason_code: str,
    reason_text: str,
) -> list[Suggestion]:
    session.add(
        Suggestion(
            post_id=post.id,
            status=SuggestionStatus.NO_CONFIDENT_MATCH,
            reason_code=reason_code,
            reason_text=reason_text,
        )
    )
    session.commit()
    return list_suggestions(session, post.id)
