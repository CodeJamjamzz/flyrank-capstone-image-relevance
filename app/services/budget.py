from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ModelCall, ModelCallStatus


class CostBudgetExceededError(RuntimeError):
    pass


def ensure_cost_budget_available(
    session: Session,
    tenant_id: UUID,
    configuration: Settings,
) -> None:
    if configuration.ai_cost_budget_usd is None:
        return

    spent = session.scalar(
        select(func.coalesce(func.sum(ModelCall.estimated_cost_usd), Decimal("0"))).where(
            ModelCall.tenant_id == tenant_id,
            ModelCall.status == ModelCallStatus.SUCCEEDED,
        )
    )
    total = Decimal(str(spent))
    if total >= configuration.ai_cost_budget_usd:
        raise CostBudgetExceededError(
            f"AI cost budget of ${configuration.ai_cost_budget_usd:.2f} is exhausted "
            f"for this tenant (recorded cost: ${total:.6f})."
        )
