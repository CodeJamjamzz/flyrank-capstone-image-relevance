from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.embeddings import GeminiEmbeddingProvider
from app.services.evaluation import (
    EvaluationReadinessError,
    load_evaluation_dataset,
    run_evaluation,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "evaluation" / "post_image_relevance.json"
REPORT_PATH = PROJECT_ROOT / "data" / "evaluation" / "evaluation-report.json"


def main() -> int:
    try:
        dataset = load_evaluation_dataset(DATASET_PATH)
        provider = GeminiEmbeddingProvider(settings)
        with SessionLocal() as session:
            report = run_evaluation(session, dataset, provider, settings)
    except (EvaluationReadinessError, OSError, ValueError) as error:
        print(f"evaluation_failed={error}")
        return 1

    REPORT_PATH.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"top_1_precision={report.top_1_precision:.4f}")
    print(f"correct_top_1={report.correct_top_1}/{report.total_cases}")
    print(f"report_path={REPORT_PATH.relative_to(PROJECT_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
