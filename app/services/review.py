from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewDecision,
    ReviewDecisionType,
    Suggestion,
    SuggestionStatus,
)


class SuggestionNotFoundError(LookupError):
    pass


class SuggestionNotReviewableError(RuntimeError):
    pass


def list_suggestions_for_review(
    session: Session,
    suggestion_status: SuggestionStatus | None,
) -> list[Suggestion]:
    statement = select(Suggestion).order_by(Suggestion.created_at.desc(), Suggestion.id)
    if suggestion_status is not None:
        statement = statement.where(Suggestion.status == suggestion_status)
    return list(session.scalars(statement))


def get_suggestion_for_review(session: Session, suggestion_id: uuid.UUID) -> Suggestion:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise SuggestionNotFoundError(f"Suggestion {suggestion_id} does not exist")
    return suggestion


def latest_review_decision(
    session: Session,
    suggestion_id: uuid.UUID,
) -> ReviewDecision | None:
    return session.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.suggestion_id == suggestion_id)
        .order_by(ReviewDecision.created_at.desc(), ReviewDecision.id.desc())
        .limit(1)
    )


def review_suggestion(
    session: Session,
    suggestion_id: uuid.UUID,
    decision: ReviewDecisionType,
    reviewer_note: str | None,
) -> Suggestion:
    suggestion = session.scalar(
        select(Suggestion).where(Suggestion.id == suggestion_id).with_for_update()
    )
    if suggestion is None:
        raise SuggestionNotFoundError(f"Suggestion {suggestion_id} does not exist")
    if suggestion.status != SuggestionStatus.PENDING_REVIEW:
        raise SuggestionNotReviewableError(
            f"Suggestion {suggestion_id} has status {suggestion.status.value} "
            "and cannot be reviewed"
        )

    session.add(
        ReviewDecision(
            suggestion_id=suggestion.id,
            decision=decision,
            reviewer_note=reviewer_note,
        )
    )
    suggestion.status = (
        SuggestionStatus.APPROVED
        if decision == ReviewDecisionType.APPROVED
        else SuggestionStatus.REJECTED
    )
    session.commit()
    session.refresh(suggestion)
    return suggestion
