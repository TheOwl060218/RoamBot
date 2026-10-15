"""Display metadata from known destinations, never additional query constraints."""

from collections.abc import Iterable, Mapping


def display_city(request: Mapping[str, object], items: Iterable[Mapping[str, object]]) -> str:
    city = str(request.get("city") or "").strip()
    if city:
        return city
    cities: list[str] = []
    for item in items:
        destination = item.get("destination")
        if isinstance(destination, Mapping):
            value = str(destination.get("city") or "").strip()
            if value and value not in cities:
                cities.append(value)
    return "、".join(cities)
