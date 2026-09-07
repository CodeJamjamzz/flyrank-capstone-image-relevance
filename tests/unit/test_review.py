from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from app.db.models import ReviewDecision, ReviewDecisionType, Suggestion, SuggestionStatus
from app.services.review import SuggestionNotReviewableError, review_suggestion


class FakeSession:
    def __init__(self, suggestion: Suggestion) -> None:
        self.suggestion = suggestion
        self.items: list[object] = []
        self.commit_count = 0

    def scalar(self, statement: object) -> Suggestion:
        del statement
        return self.suggestion

    def add(self, item: object) -> None:
        self.items.append(item)

    def commit(self) -> None:
        self.commit_count += 1

    def refresh(self, item: object) -> None:
        del item


def build_suggestion(suggestion_status: SuggestionStatus) -> Suggestion:
    return Suggestion(
        id=uuid.uuid4(),
        post_id=uuid.uuid4(),
        status=suggestion_status,
        reason_code="matched",
        reason_text="Candidate passed similarity and subject-mismatch checks.",
        created_at=datetime.now(UTC),
    )


def test_review_approves_pending_suggestion_and_records_decision() -> None:
    suggestion = build_suggestion(SuggestionStatus.PENDING_REVIEW)
    session = FakeSession(suggestion)

    reviewed = review_suggestion(
        cast(object, session),
        suggestion.id,
        ReviewDecisionType.APPROVED,
        "Correct image.",
    )

    decision = next(item for item in session.items if isinstance(item, ReviewDecision))
    assert reviewed.status == SuggestionStatus.APPROVED
    assert decision.suggestion_id == suggestion.id
    assert decision.decision == ReviewDecisionType.APPROVED
    assert decision.reviewer_note == "Correct image."
    assert session.commit_count == 1


def test_review_rejects_pending_suggestion() -> None:
    suggestion = build_suggestion(SuggestionStatus.PENDING_REVIEW)
    session = FakeSession(suggestion)

    reviewed = review_suggestion(
        cast(object, session), suggestion.id, ReviewDecisionType.REJECTED, None
    )

    assert reviewed.status == SuggestionStatus.REJECTED


@pytest.mark.parametrize(
    "suggestion_status",
    [SuggestionStatus.APPROVED, SuggestionStatus.REJECTED, SuggestionStatus.NO_CONFIDENT_MATCH],
)
def test_review_refuses_final_or_machine_rejected_suggestion(
    suggestion_status: SuggestionStatus,
) -> None:
    suggestion = build_suggestion(suggestion_status)
    session = FakeSession(suggestion)

    with pytest.raises(SuggestionNotReviewableError):
        review_suggestion(cast(object, session), suggestion.id, ReviewDecisionType.APPROVED, None)

    assert session.items == []
    assert session.commit_count == 0
