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


def next_poll_delay_seconds(
    processed: bool,
    configuration: Settings,
    rate_limited: bool = False,
    budget_limited: bool = False,
) -> int:
    if budget_limited:
        return configuration.ai_budget_backoff_seconds
    if rate_limited:
        return configuration.image_worker_rate_limit_backoff_seconds
    if processed:
        return configuration.image_worker_processing_delay_seconds
    return configuration.image_worker_poll_interval_seconds


def run_forever() -> None:
    provider = GeminiVisionProvider(settings)
    embedding_provider = GeminiEmbeddingProvider(settings)
    while True:
        try:
            with SessionLocal() as session:
                outcome = process_next_image(
                    session, provider, settings, PROJECT_ROOT, embedding_provider
                )
        except Exception:
            logger.exception("Image worker failed while processing an image")
            outcome = None
        if outcome is not None and outcome.budget_limited:
            logger.warning(
                "AI cost budget reached; pausing for %s seconds.",
                settings.ai_budget_backoff_seconds,
            )
        elif outcome is not None and outcome.rate_limited:
            logger.warning(
                "Vision provider rate limited the worker; pausing for %s seconds.",
                settings.image_worker_rate_limit_backoff_seconds,
            )
        time.sleep(
            next_poll_delay_seconds(
                outcome.processed if outcome is not None else False,
                settings,
                rate_limited=outcome.rate_limited if outcome is not None else False,
                budget_limited=outcome.budget_limited if outcome is not None else False,
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
