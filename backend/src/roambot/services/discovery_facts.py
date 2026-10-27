"""Read-only fact computation from a frozen request, with bounded provider reads."""

from concurrent.futures import ThreadPoolExecutor

from roambot.domain.discovery_execution import BatchInput, BatchResult
from roambot.domain.models import Coordinate
from roambot.providers.protocols import ProviderError


def freeze_facts(run, sequence, ids, revision):
    return BatchInput.freeze(
        run.scope,
        revision,
        sequence,
        {
            "execution_id": run.execution_id,
            "ids": ids,
            "places": [run.places[key] for key in ids],
            "center": run.center.model_dump() if run.center else None,
            "context": run.context.model_dump(mode="json"),
        },
    )


def collect_facts(batch, maps, weather, cache, budget, interval=0):
    data = batch.payload()
    tasks = [
        (kind, place)
        for place in data["places"]
        for kind, enabled in (
            ("route", bool(data["center"])),
            ("weather", bool(data["context"]["start_date"])),
        )
        if enabled
    ]

    def fetch(item):
        kind, place = item
        key = place["id"]
        budget.check()
        try:
            if kind == "route":
                cache_key = [
                    key,
                    data["center"],
                    place["coordinate"],
                    data["context"]["travel_mode"],
                ]

                def load():
                    cache.throttle_map(interval)
                    budget.check()
                    return maps.route(
                        Coordinate(**data["center"]), place, data["context"]["travel_mode"]
                    )

                value, hit = cache.get_or_load(batch.identity, "route-v1", cache_key, 300, load)
            else:
                context = data["context"]
                cache_key = [place["coordinate"], context["start_date"], context["end_date"]]

                def load():
                    from datetime import date

                    budget.check()
                    return [
                        day.model_dump(mode="json")
                        for day in weather.daily(
                            Coordinate(**place["coordinate"]),
                            date.fromisoformat(context["start_date"]),
                            date.fromisoformat(context["end_date"]),
                        )
                    ]

                value, hit = cache.get_or_load(batch.identity, "weather-v1", cache_key, 600, load)
            return {"kind": kind, "id": key, "value": value, "hit": hit}
        except (ProviderError, ValueError, KeyError) as error:
            return {
                "kind": kind,
                "id": key,
                "value": {"unavailable": True},
                "hit": False,
                "error": getattr(error, "code", "unavailable"),
            }

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="discovery-facts") as pool:
        values = list(pool.map(fetch, tasks))
    budget.check()
    return BatchResult.freeze(batch, {"values": values})
