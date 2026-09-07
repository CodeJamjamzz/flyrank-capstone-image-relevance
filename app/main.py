import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Image, ImageMetadata, Post, Suggestion, SuggestionStatus
from app.db.session import get_session
from app.schemas.contracts import (
    PostCreateRequest,
    PostCreateResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    SuggestionInspectionResponse,
    SuggestionListResponse,
    SuggestionResponse,
    SuggestionReviewListResponse,
)
from app.services.embeddings import (
    EmbeddingProvider,
    GeminiEmbeddingProvider,
    embed_post_if_needed,
    latest_embedding_for_post,
)
from app.services.matching import create_suggestions_if_needed, recognize_subject
from app.services.review import (
    SuggestionNotFoundError,
    SuggestionNotReviewableError,
    get_suggestion_for_review,
    latest_review_decision,
    list_suggestions_for_review,
    review_suggestion,
)

app = FastAPI(title="FlyRank Image Relevance")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def get_embedding_provider() -> EmbeddingProvider:
    try:
        return GeminiEmbeddingProvider(settings)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@app.post("/posts", response_model=PostCreateResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreateRequest,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> PostCreateResponse:
    post = Post(text=payload.text, recognized_subject=recognize_subject(payload.text))
    session.add(post)
    session.flush()
    embedding_ready = embed_post_if_needed(session, post.id, post.text, provider, settings)
    session.refresh(post)
    return PostCreateResponse(
        id=post.id,
        text=post.text,
        recognized_subject=post.recognized_subject,
        embedding_ready=embedding_ready,
        created_at=post.created_at,
    )


@app.get("/posts/{post_id}/images", response_model=SuggestionListResponse)
def get_post_images(
    post_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> SuggestionListResponse:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if latest_embedding_for_post(session, post.id) is None:
        provider = get_embedding_provider()
        embed_post_if_needed(session, post.id, post.text, provider, settings)

    suggestions = create_suggestions_if_needed(session, post.id, settings)
    image_ids = [
        suggestion.image_id for suggestion in suggestions if suggestion.image_id is not None
    ]
    images = {
        image.id: image for image in session.query(Image).filter(Image.id.in_(image_ids)).all()
    }
    return SuggestionListResponse(
        post_id=post.id,
        suggestions=[
            _suggestion_response(
                suggestion,
                images.get(suggestion.image_id) if suggestion.image_id is not None else None,
                rank,
            )
            for rank, suggestion in enumerate(suggestions, start=1)
        ],
    )


@app.get("/suggestions", response_model=SuggestionReviewListResponse)
def list_review_suggestions(
    session: Annotated[Session, Depends(get_session)],
    suggestion_status: Annotated[
        SuggestionStatus | None, Query()
    ] = SuggestionStatus.PENDING_REVIEW,
) -> SuggestionReviewListResponse:
    suggestions = list_suggestions_for_review(session, suggestion_status)
    return SuggestionReviewListResponse(
        suggestions=[
            _suggestion_inspection_response(session, suggestion) for suggestion in suggestions
        ]
    )


@app.get("/suggestions/{suggestion_id}", response_model=SuggestionInspectionResponse)
def inspect_suggestion(
    suggestion_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> SuggestionInspectionResponse:
    try:
        suggestion = get_suggestion_for_review(session, suggestion_id)
    except SuggestionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        ) from error
    return _suggestion_inspection_response(session, suggestion)


@app.post("/suggestions/{suggestion_id}/review", response_model=SuggestionInspectionResponse)
def submit_review_decision(
    suggestion_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    session: Annotated[Session, Depends(get_session)],
) -> SuggestionInspectionResponse:
    try:
        suggestion = review_suggestion(
            session,
            suggestion_id,
            payload.decision,
            payload.reviewer_note,
        )
    except SuggestionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        ) from error
    except SuggestionNotReviewableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _suggestion_inspection_response(session, suggestion)


def _suggestion_response(
    suggestion: Suggestion,
    image: Image | None,
    rank: int,
) -> SuggestionResponse:
    return SuggestionResponse(
        id=suggestion.id,
        post_id=suggestion.post_id,
        image_id=suggestion.image_id,
        image_file_path=image.file_path if image is not None else None,
        image_source_url=image.source_url if image is not None else None,
        rank=rank if suggestion.image_id is not None else None,
        similarity_score=float(suggestion.similarity_score)
        if suggestion.similarity_score is not None
        else None,
        status=suggestion.status,
        reason_code=suggestion.reason_code,
        reason_text=suggestion.reason_text,
        created_at=suggestion.created_at,
    )


def _suggestion_inspection_response(
    session: Session,
    suggestion: Suggestion,
) -> SuggestionInspectionResponse:
    post = session.get(Post, suggestion.post_id)
    if post is None:
        raise RuntimeError("Suggestion post no longer exists")
    image = session.get(Image, suggestion.image_id) if suggestion.image_id is not None else None
    metadata = (
        session.scalar(select(ImageMetadata).where(ImageMetadata.image_id == image.id))
        if image is not None
        else None
    )
    review_decision = latest_review_decision(session, suggestion.id)
    return SuggestionInspectionResponse(
        id=suggestion.id,
        post_id=suggestion.post_id,
        post_text=post.text,
        image_id=suggestion.image_id,
        image_file_path=image.file_path if image is not None else None,
        image_source_url=image.source_url if image is not None else None,
        image_primary_subject=metadata.primary_subject if metadata is not None else None,
        similarity_score=float(suggestion.similarity_score)
        if suggestion.similarity_score is not None
        else None,
        status=suggestion.status,
        reason_code=suggestion.reason_code,
        reason_text=suggestion.reason_text,
        review_decision=(
            ReviewDecisionResponse.model_validate(review_decision)
            if review_decision is not None
            else None
        ),
        created_at=suggestion.created_at,
    )
