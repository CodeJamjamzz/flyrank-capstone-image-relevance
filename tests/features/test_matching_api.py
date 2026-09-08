from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.db.models import Post, Suggestion, SuggestionStatus
from app.db.session import get_session
from app.main import app, get_embedding_provider


class FakeSession:
    def __init__(self, post: Post | None = None) -> None:
        self.post = post

    def add(self, item: object) -> None:
        if isinstance(item, Post):
            item.id = uuid.uuid4()
            item.created_at = datetime.now(UTC)
            self.post = item

    def flush(self) -> None:
        return None

    def refresh(self, item: object) -> None:
        del item

    def get(self, model: type[object], identifier: uuid.UUID) -> Post | None:
        del model, identifier
        return self.post

    def scalar(self, statement: object) -> Post | None:
        del statement
        return self.post

    def query(self, model: type[object]) -> FakeQuery:
        del model
        return FakeQuery()


class FakeQuery:
    def filter(self, *expressions: object) -> FakeQuery:
        del expressions
        return self

    def all(self) -> list[object]:
        return []


def test_create_post_creates_embedding_ready_response(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
    monkeypatch.setitem(app.dependency_overrides, get_embedding_provider, lambda: object())
    monkeypatch.setattr(main_module, "embed_post_if_needed", lambda *args: True)

    with TestClient(app) as client:
        response = client.post("/posts", json={"text": "A Vulpes vulpes in snow"})

    assert response.status_code == 201
    assert response.json()["recognized_subject"] == "red fox"
    assert response.json()["embedding_ready"] is True


def test_post_endpoint_rejects_invalid_text() -> None:
    with TestClient(app) as client:
        response = client.post("/posts", json={"text": ""})

    assert response.status_code == 422


def test_suggestion_endpoint_returns_cached_no_match(monkeypatch) -> None:
    post = Post(id=uuid.uuid4(), text="A red fox in snow")
    suggestion = Suggestion(
        id=uuid.uuid4(),
        post_id=post.id,
        status=SuggestionStatus.NO_CONFIDENT_MATCH,
        reason_code="corpus_embedding_unavailable",
        reason_text="No confident match: no accepted image embeddings are available.",
        created_at=datetime.now(UTC),
    )
    session = FakeSession(post)
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
    monkeypatch.setattr(main_module, "latest_embedding_for_post", lambda *args: object())
    monkeypatch.setattr(
        main_module,
        "create_suggestions_if_needed",
        lambda *args: [suggestion],
    )

    with TestClient(app) as client:
        response = client.get(f"/posts/{post.id}/images")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestions"][0]["status"] == "no_confident_match"
    assert payload["suggestions"][0]["rank"] is None


def test_suggestion_endpoint_returns_not_found_for_unknown_post(monkeypatch) -> None:
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: FakeSession())

    with TestClient(app) as client:
        response = client.get(f"/posts/{uuid.uuid4()}/images")

    assert response.status_code == 404


class ExistingPostSession(FakeSession):
    def scalar(self, statement: object) -> Post | None:
        del statement
        return self.post


def test_create_post_returns_existing_result_for_same_idempotency_key(monkeypatch) -> None:
    post = Post(
        id=uuid.uuid4(),
        text="A red fox in snow",
        recognized_subject="red fox",
        idempotency_key="post-retry-1",
        created_at=datetime.now(UTC),
    )
    session = ExistingPostSession(post)
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
    monkeypatch.setitem(app.dependency_overrides, get_embedding_provider, lambda: object())
    monkeypatch.setattr(main_module, "latest_embedding_for_post", lambda *args: object())
    monkeypatch.setattr(
        main_module,
        "embed_post_if_needed",
        lambda *args: pytest.fail("duplicate request must not create a second embedding"),
    )

    with TestClient(app) as client:
        response = client.post(
            "/posts",
            json={"text": "A red fox in snow"},
            headers={"Idempotency-Key": "post-retry-1"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(post.id)


def test_create_post_rejects_idempotency_key_reused_for_different_text(monkeypatch) -> None:
    post = Post(
        id=uuid.uuid4(),
        text="A red fox in snow",
        idempotency_key="post-retry-1",
        created_at=datetime.now(UTC),
    )
    session = ExistingPostSession(post)
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
    monkeypatch.setitem(app.dependency_overrides, get_embedding_provider, lambda: object())

    with TestClient(app) as client:
        response = client.post(
            "/posts",
            json={"text": "A wolf in snow"},
            headers={"Idempotency-Key": "post-retry-1"},
        )

    assert response.status_code == 409


def test_create_post_scopes_the_record_to_the_request_tenant(monkeypatch) -> None:
    session = FakeSession()
    tenant_id = uuid.uuid4()
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
    monkeypatch.setitem(app.dependency_overrides, get_embedding_provider, lambda: object())
    monkeypatch.setattr(main_module, "embed_post_if_needed", lambda *args: True)

    with TestClient(app) as client:
        response = client.post(
            "/posts",
            json={"text": "A red fox in snow"},
            headers={"X-Tenant-ID": str(tenant_id)},
        )

    assert response.status_code == 201
    assert session.post is not None
    assert session.post.tenant_id == tenant_id
