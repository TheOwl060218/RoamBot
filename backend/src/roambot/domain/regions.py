"""Independent, versioned administrative directory; never an AMap table cache."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roambot.domain.models import Destination


@lru_cache(maxsize=1)
def _directory() -> dict:
    return json.loads((Path(__file__).parent / 'data' / 'regions.json').read_text('utf-8'))


def region_catalog() -> dict:
    return deepcopy({key: value for key, value in _directory().items() if key != 'ancestry'})


@lru_cache(maxsize=1)
def _selectable() -> dict[str, dict]:
    return {row['adcode']: row for row in _directory()['regions']}


def normalize_destination_regions(values: list[str]) -> list[str]:
    rows = _selectable()
    if len(values) > len(rows):
        raise ValueError('too many destination regions')
    if any(code not in rows for code in values):
        raise ValueError('unknown destination region; please select a listed province or city')
    selected = set(values)
    return sorted(code for code in selected if rows[code]['level'] == 'province'
                  or rows[code]['province_adcode'] not in selected)


def resolve_region_codes(adcode: str | None, pcode: str | None) -> tuple[str | None, str | None]:
    """Unknown codes stay unknown; an explicit known province may still be retained."""
    ancestry = _directory()['ancestry']
    if adcode in ancestry:
        province, city = ancestry[adcode]
        # Conflicting metadata cannot be trusted for hard geographic filtering.
        if pcode and pcode != province:
            return None, None
        return province, city
    province_row = _selectable().get(pcode or '')
    if province_row and province_row['level'] == 'province':
        return pcode, None
    return None, None


def matches_destination_regions(destination: Destination, regions: tuple[str, ...]) -> bool:
    if not regions:
        return True
    return any(code in {destination.province_adcode, destination.city_adcode}
               for code in regions)


def missing_region_membership(destination: Destination, regions: tuple[str, ...]) -> bool:
    rows = _selectable()
    return bool(regions) and (destination.province_adcode is None
        or any(rows[code]['level'] == 'city'
               and rows[code]['province_adcode'] == destination.province_adcode
               for code in regions) and destination.city_adcode is None)
