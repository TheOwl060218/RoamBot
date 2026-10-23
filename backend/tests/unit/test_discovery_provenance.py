"""Redundant, verifiable provenance is not an unknown semantic instruction."""
import copy

import pytest
from pydantic import ValidationError
from roambot.providers.discovery import normalized_arguments
from roambot.services.discovery_tasks import TaskIntake


def payload():
    return {'intent': 'search', 'context': {'region': '苏州', 'region_quote': '苏州'},
            'temporal': None, 'directions': []}


def test_verbatim_provenance_for_existing_scalar_does_not_destroy_valid_native_intake():
    raw = payload()
    before = copy.deepcopy(raw)
    value = TaskIntake.model_validate(normalized_arguments(TaskIntake, raw, user_texts=('去苏州看看',)))
    assert value.context.region == '苏州'
    assert raw == before


@pytest.mark.parametrize('change', ['unquoted', 'semantic', 'missing_base', 'no_user_text'])
def test_normalization_does_not_discard_unknown_semantics_or_unverified_metadata(change):
    raw = payload()
    texts = ('去苏州看看',)
    if change == 'unquoted': raw['context']['region_quote'] = '杭州'
    elif change == 'semantic': raw['context']['include_other_cities'] = True
    elif change == 'missing_base': raw['context'].pop('region')
    else: texts = ()
    with pytest.raises(ValidationError):
        TaskIntake.model_validate(normalized_arguments(TaskIntake, raw, user_texts=texts))


def test_canonical_quote_is_not_removed_even_if_not_in_user_text():
    raw = payload()
    raw['context'].update(origin='苏州站', origin_quote='虚构引用')
    value = TaskIntake.model_validate(normalized_arguments(TaskIntake, raw, user_texts=('去苏州看看',)))
    assert value.context.origin_quote == '虚构引用'  # Existing execution-layer provenance check must still reject it.
