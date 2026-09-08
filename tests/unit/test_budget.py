import uuid
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.tenancy import DEFAULT_TENANT_ID
from app.services.budget import CostBudgetExceededError, ensure_cost_budget_available


class BudgetSession:
    def __init__(self, spent: Decimal) -> None:
        self.spent = spent

    def scalar(self, statement: object) -> Decimal:
        del statement
        return self.spent


def test_cost_budget_allows_spending_below_limit() -> None:
    ensure_cost_budget_available(
        cast(Session, BudgetSession(Decimal("0.50"))),
        DEFAULT_TENANT_ID,
        Settings(ai_cost_budget_usd=Decimal("1.00")),
    )


def test_cost_budget_stops_calls_at_limit() -> None:
    with pytest.raises(CostBudgetExceededError, match="AI cost budget"):
        ensure_cost_budget_available(
            cast(Session, BudgetSession(Decimal("1.00"))),
            uuid.uuid4(),
            Settings(ai_cost_budget_usd=Decimal("1.00")),
        )


def test_cost_budget_can_be_disabled_for_local_free_tier_runs() -> None:
    ensure_cost_budget_available(
        cast(Session, BudgetSession(Decimal("999.00"))),
        DEFAULT_TENANT_ID,
        Settings(ai_cost_budget_usd=None),
    )
