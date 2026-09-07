from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.db.models import Image, ImageProcessingStatus
from app.db.session import SessionLocal
from app.services.embeddings import GeminiEmbeddingProvider, embed_image_if_needed


def main() -> int:
    provider = GeminiEmbeddingProvider(settings)
    succeeded = 0
    failed = 0
    with SessionLocal() as session:
        images = list(
            session.scalars(
                select(Image)
                .where(Image.processing_status == ImageProcessingStatus.ACCEPTED)
                .order_by(Image.created_at, Image.id)
            )
        )
        for image in images:
            if embed_image_if_needed(session, image, provider, settings):
                succeeded += 1
            else:
                failed += 1

    print(f"image_embeddings_succeeded={succeeded}")
    print(f"image_embeddings_failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
