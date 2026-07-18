import pytest

from roambot.providers.budget import (
    ProviderBudget,
    ProviderBudgetExceeded,
    ProviderOperation,
)


def test_each_provider_operation_has_an_independent_limit() -> None:
    budget = ProviderBudget(
        {
            ProviderOperation.GEOCODE: 3,
            ProviderOperation.POI_SEARCH: 6,
            ProviderOperation.WEATHER: 5,
            ProviderOperation.DISTANCE: 5,
            ProviderOperation.LLM: 1,
        }
    )

    for operation, limit in budget.limits.items():
        for _ in range(limit):
            budget.consume(operation)
        assert budget.count(operation) == limit

        with pytest.raises(ProviderBudgetExceeded) as captured:
            budget.consume(operation)
        assert operation.value in str(captured.value)
        assert str(limit) in str(captured.value)
        assert budget.count(operation) == limit


def test_new_budget_starts_with_zero_counters() -> None:
    limits = {operation: 1 for operation in ProviderOperation}
    first = ProviderBudget(limits)
    first.consume(ProviderOperation.LLM)

    second = ProviderBudget(limits)
    assert all(second.count(operation) == 0 for operation in ProviderOperation)


def test_budget_rejects_missing_or_negative_limits() -> None:
    with pytest.raises(ValueError):
        ProviderBudget({ProviderOperation.GEOCODE: 1})
    with pytest.raises(ValueError):
        ProviderBudget({operation: -1 for operation in ProviderOperation})
