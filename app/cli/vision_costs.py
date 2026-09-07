from __future__ import annotations

from decimal import Decimal

from app.db.session import SessionLocal
from app.services.costs import summarize_vision_costs


def format_cost(value: Decimal) -> str:
    return f"${value:.6f}"


def main() -> int:
    with SessionLocal() as session:
        summaries = summarize_vision_costs(session)

    if not summaries:
        print("No vision model calls recorded.")
        return 0

    print("model,status,calls,input_units,output_units,estimated_cost_usd")
    for summary in summaries:
        print(
            f"{summary.model_name},{summary.status},{summary.call_count},"
            f"{summary.input_units},{summary.output_units},{format_cost(summary.estimated_cost_usd)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
