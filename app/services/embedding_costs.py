from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelCall, ModelOperation


def format_cost(value: Decimal) -> str:
    return f"${value:.6f}"


def print_embedding_costs(session: Session) -> None:
    model_calls = session.scalars(
        select(ModelCall)
        .where(ModelCall.operation == ModelOperation.EMBEDDING)
        .order_by(ModelCall.model_name, ModelCall.status)
    )
    print("model,status,calls,input_units,estimated_cost_usd")
    summaries: dict[tuple[str, str], tuple[int, int, Decimal]] = {}
    for model_call in model_calls:
        key = (model_call.model_name, model_call.status.value)
        calls, input_units, cost = summaries.get(key, (0, 0, Decimal("0")))
        summaries[key] = (
            calls + 1,
            input_units + model_call.input_units,
            cost + model_call.estimated_cost_usd,
        )
    for (model_name, status), (calls, input_units, cost) in summaries.items():
        print(f"{model_name},{status},{calls},{input_units},{format_cost(cost)}")
