from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ModelCall, ModelOperation


@dataclass
class VisionCostSummary:
    model_name: str
    status: str
    call_count: int = 0
    input_units: int = 0
    output_units: int = 0
    estimated_cost_usd: Decimal = Decimal("0")


def summarize_vision_costs(session: Session) -> list[VisionCostSummary]:
    summaries: dict[tuple[str, str], VisionCostSummary] = {}
    model_calls = session.scalars(
        select(ModelCall)
        .where(ModelCall.operation == ModelOperation.VISION)
        .order_by(ModelCall.model_name)
    )
    for model_call in model_calls:
        key = (model_call.model_name, model_call.status.value)
        summary = summaries.setdefault(
            key,
            VisionCostSummary(model_name=model_call.model_name, status=model_call.status.value),
        )
        summary.call_count += 1
        summary.input_units += model_call.input_units
        summary.output_units += model_call.output_units
        summary.estimated_cost_usd += model_call.estimated_cost_usd
    return sorted(summaries.values(), key=lambda summary: (summary.model_name, summary.status))
