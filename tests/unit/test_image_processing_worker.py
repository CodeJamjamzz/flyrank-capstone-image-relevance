from app.core.config import Settings
from app.workers.image_processing_worker import next_poll_delay_seconds


def test_next_poll_delay_uses_processing_delay_after_an_attempt() -> None:
    configuration = Settings(
        image_worker_poll_interval_seconds=5,
        image_worker_processing_delay_seconds=30,
    )

    assert next_poll_delay_seconds(processed=True, configuration=configuration) == 30
    assert next_poll_delay_seconds(processed=False, configuration=configuration) == 5
