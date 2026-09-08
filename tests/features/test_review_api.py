from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.main as main_module
from app.db.models import Suggestion, SuggestionStatus
from app.db.session import get_session
from app.main import app
from app.schemas.contracts import SuggestionInspectionResponse
from app.services.review import SuggestionNotFoundError, SuggestionNotReviewableError


class FakeSession:
    pass


def inspection_response(suggestion: Suggestion) -> SuggestionInspectionResponse:
    return SuggestionInspectionResponse(
        id=suggestion.id,
        post_id=suggestion.post_id,
        post_text="A red fox in snow",
        image_id=None,
        image_file_path=None,
        image_source_url=None,
        image_primary_subject=None,
        similarity_score=None,
        status=suggestion.status,
        reason_code=suggestion.reason_code,
        reason_text=suggestion.reason_text,
        review_decision=None,
        created_at=suggestion.created_at,
    )


def build_suggestion(suggestion_status: SuggestionStatus) -> Suggestion:
    return Suggestion(
        id=uuid.uuid4(),
        post_id=uuid.uuid4(),
        status=suggestion_status,
        reason_code="matched",
        reason_text="Candidate passed checks.",
        created_at=datetime.now(UTC),
    )


def test_list_review_suggestions_defaults_to_pending(monkeypatch) -> None:
    suggestion = build_suggestion(SuggestionStatus.PENDING_REVIEW)
    captured_status: list[SuggestionStatus | None] = []
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())
    monkeypatch.setattr(
        main_module,
        "list_suggestions_for_review",
        lambda session, suggestion_status, tenant_id: (
            captured_status.append(suggestion_status) or [suggestion]
        ),
    )
    monkeypatch.setattr(
        main_module,
        "_suggestion_inspection_response",
        lambda session, item: inspection_response(item),
    )

    with TestClient(app) as client:
        response = client.get("/suggestions")

    assert response.status_code == 200
    assert captured_status == [SuggestionStatus.PENDING_REVIEW]
    assert response.json()["suggestions"][0]["id"] == str(suggestion.id)


def test_inspect_unknown_suggestion_returns_not_found(monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())
    monkeypatch.setattr(
        main_module,
        "get_suggestion_for_review",
        lambda *args: (_ for _ in ()).throw(SuggestionNotFoundError()),
    )

    with TestClient(app) as client:
        response = client.get(f"/suggestions/{uuid.uuid4()}")

    assert response.status_code == 404


def test_review_approves_pending_suggestion(monkeypatch) -> None:
    suggestion = build_suggestion(SuggestionStatus.APPROVED)
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())
    monkeypatch.setattr(main_module, "review_suggestion", lambda *args: suggestion)
    monkeypatch.setattr(
        main_module,
        "_suggestion_inspection_response",
        lambda session, item: inspection_response(item),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/suggestions/{suggestion.id}/review",
            json={"decision": "approved", "reviewer_note": "Correct image."},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_review_returns_conflict_for_final_suggestion(monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())
    monkeypatch.setattr(
        main_module,
        "review_suggestion",
        lambda *args: (_ for _ in ()).throw(SuggestionNotReviewableError("Already reviewed")),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/suggestions/{uuid.uuid4()}/review",
            json={"decision": "approved"},
        )

    assert response.status_code == 409


def test_review_rejects_invalid_payload(monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())

    with TestClient(app) as client:
        response = client.post(f"/suggestions/{uuid.uuid4()}/review", json={"decision": "invalid"})

    assert response.status_code == 422
