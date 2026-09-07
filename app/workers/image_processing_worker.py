from __future__ import annotations

import logging
import time
from pathlib import Path

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.services.embeddings import GeminiEmbeddingProvider
from app.services.image_processing import process_next_image
from app.services.vision import GeminiVisionProvider

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def next_poll_delay_seconds(processed: bool, configuration: Settings) -> int:
    if processed:
        return configuration.image_worker_processing_delay_seconds
    return configuration.image_worker_poll_interval_seconds


def run_forever() -> None:
    provider = GeminiVisionProvider(settings)
    embedding_provider = GeminiEmbeddingProvider(settings)
    while True:
        try:
            with SessionLocal() as session:
                processed = process_next_image(
                    session, provider, settings, PROJECT_ROOT, embedding_provider
                )
        except Exception:
            logger.exception("Image worker failed while processing an image")
            processed = False
        time.sleep(next_poll_delay_seconds(processed, settings))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
