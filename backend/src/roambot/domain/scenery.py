from collections.abc import Mapping

from roambot.domain.models import SceneryType
from roambot.domain.scenery_rules import NAME_TERMS, NAME_TYPE_PREFIXES, TYPE_TERMS


def classify_scenery(
    name: str,
    type_name: str,
    type_code: str,
    overrides: Mapping[str, frozenset[SceneryType]],
) -> frozenset[SceneryType]:
    if name in overrides:
        return overrides[name]

    tags: set[SceneryType] = set()
    for tag, terms in TYPE_TERMS.items():
        if any(term in type_name for term in terms):
            tags.add(tag)
    for tag, terms in NAME_TERMS.items():
        if type_code.startswith(NAME_TYPE_PREFIXES[tag]) and any(term in name for term in terms):
            tags.add(tag)
    return frozenset(tags)
