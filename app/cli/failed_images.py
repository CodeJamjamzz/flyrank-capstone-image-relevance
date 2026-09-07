from __future__ import annotations

from sqlalchemy import select

from app.db.models import Image, ImageProcessingStatus, ProcessingAttempt
from app.db.session import SessionLocal


def main() -> int:
    with SessionLocal() as session:
        images = session.scalars(
            select(Image)
            .where(Image.processing_status == ImageProcessingStatus.FAILED)
            .order_by(Image.file_path)
        ).all()
        print("file_path,retry_count,error_code,error_message")
        for image in images:
            attempt = session.scalar(
                select(ProcessingAttempt)
                .where(ProcessingAttempt.image_id == image.id)
                .order_by(ProcessingAttempt.attempt_number.desc())
                .limit(1)
            )
            error_code = attempt.error_code if attempt is not None else ""
            error_message = attempt.error_message if attempt is not None else ""
            print(f"{image.file_path},{image.retry_count},{error_code},{error_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
