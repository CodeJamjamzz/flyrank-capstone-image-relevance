from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import Image, ImageProcessingStatus
from app.db.session import SessionLocal


def main() -> int:
    with SessionLocal() as session:
        images = session.scalars(
            select(Image).where(Image.processing_status == ImageProcessingStatus.FAILED)
        ).all()
        for image in images:
            image.processing_status = ImageProcessingStatus.RETRY_SCHEDULED
            image.next_retry_at = datetime.now(UTC)
        session.commit()
    print(f"Requeued failed images: {len(images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
