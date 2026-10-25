"""Plan once, retrieve in bounded parallel batches, then compose grounded cards."""

import copy
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from roambot.domain.discovery import (
    EvidenceNeed,
    ProposedCard,
    Publish,
    RetrievalPlan,
    SearchContext,
    VenueSelection,
)
from roambot.domain.models import Coordinate
from roambot.domain.business_tools import INTAKE_TOOLS
from roambot.providers.discovery import arrival_coordinate, source_mentions_place
from roambot.providers.protocols import ProviderError
from roambot.services.discovery import DiscoveryRun, model_tool_view
from roambot.services.discovery_grounding import (
    candidate_view, can_evaluate_map, cited_sources, entity_supported, referenced_passages, unsuitable_ids,
)
from roambot.services.discovery_criteria import collection_assessments, criterion_view, supported_criteria
from roambot.services.discovery_selection import select_places, select_retrieved_places, select_sources
from roambot.services.discovery_scheduling import assessment_batch_size, initial_batch_size
from roambot.services.discovery_revision import validated_revisions
from roambot.services.discovery_intent import compile_intent, requirement_groups, temporal_updates

logger = logging.getLogger(__name__)


class Stopped(Exception):
    pass


class DiscoveryWorkflow(DiscoveryRun):
    def __init__(
        self,
        body,
        maps,
        weather,
        search,
        model,
        cache,
        scope,
        previous=None,
        source="live",
        reviewer=None,
        map_interval=0,
        knowledge=None,
    ):
        super().__init__(body, maps, weather, search, None, previous, source=source)
        self.model, self.cache, self.scope = model, cache, scope
        self.previous = previous or {}
        self.reviewer = reviewer
        self.review = self.review_cards if reviewer else None
        self.metrics = {"model_calls": 0, "cache_hits": 0, "cache_misses": 0, "stages": {}}
        self.metrics_lock = threading.Lock()
        self.plan = None
        self.map_interval = map_interval
        self.knowledge = knowledge
        self.metrics.update(public_place_hits=0, web_attempts=0, rejected_cards=0)
        self.web_seen = set()
        self.evidence_query = None
        self.evidence_needs = []
        self.fresh_source_urls = set()
        self.nominated_ids = []
        self.structural_rejections = set()
        self.unsuitable = set()
        self.review_inputs = {}
        self.public_groups = []
        self.covered_directions = set()
        self.collection_assessments = {}
        self.pending_nomination = False
        self.map_results = []

    def bind_scope(self, actor):
        self.scope = actor

    def snapshot(self):
        result = super().snapshot()
        with self.metrics_lock:
            result["metrics"] = copy.deepcopy(self.metrics)
        result["workflow"] = "adaptive-v2"
        result["intent"] = self.plan.intent if self.plan else None
        result["metrics"]["web_requests"] = getattr(self.search, "request_count", None)
        result["metrics"]["search_credits"] = (
            self.search.reported_credits
            if getattr(self.search, "usage_reported", False)
            and self.search.usage_response_count == self.search.request_count
            else 0
            if self.metrics["web_attempts"] == 0
            else None
        )
        return result

    def check(self):
        if self.cancelled.is_set():
            raise Stopped()
        if time.monotonic() - self.started > 120:
            raise Stopped("deadline")

    def measured(self, stage, call):
        self.check()
        start = time.monotonic()
        try:
            return call()
        finally:
            with self.metrics_lock:
                times = self.metrics["stages"]
                times[stage] = times.get(stage, 0) + round((time.monotonic() - start) * 1000)

    def model_call(self, stage, call):
        # A single malformed-response repair is allowed; no free-running tool loop.
        for attempt in range(2):
            self.check()
            with self.metrics_lock:
                if self.metrics["model_calls"] >= 10:
                    raise Stopped("model_budget")
                self.metrics["model_calls"] += 1
            try:
                return self.measured(stage, call)
            except ProviderError as error:
                if attempt or error.code != "bad_response":
                    raise
                self.errors.append({"tool": stage, "code": "format_repair"})

    def cached(self, kind, key, ttl, load):
        self.check()
        if not self.scope:
            raise ValueError("Cache identity must be bound before execution")
        value, hit = self.cache.get_or_load(self.scope, kind, key, ttl, load)
        with self.metrics_lock:
            self.metrics["cache_hits" if hit else "cache_misses"] += 1
        return value

    def parallel(self, stage, items, call):
        self.check()
        result = [None] * len(items)
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="discovery-fetch") as pool:
            futures = {pool.submit(call, item): i for i, item in enumerate(items)}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    result[index] = future.result()
                except Stopped:
                    raise
                except (ProviderError, ValueError, KeyError) as error:
                    self.errors.append(
                        {"tool": stage, "code": getattr(error, "code", "unavailable")}
                    )
        self.check()
        return result

    def map_search(self, query):
        center = None if self.context.region else self.center
        return self.cached(
            "map-search-v2",
            [
                query,
                self.context.region,
                center.model_dump() if center else None,
                self.context.max_distance_km,
            ],
            86400,
            lambda: self.map_request(
                lambda: self.maps.search(
                    query, self.context.region, center, self.context.max_distance_km
                )
            ),
        )

    def map_request(self, load):
        self.cache.throttle_map(self.map_interval)
        self.check()
        return load()

    def web_search(self, query):
        area = self.context.region or self.context.origin or self.center_name
        scoped = " ".join(value for value in (area, query) if value)
        self.web_seen.add(query)

        def search():
            with self.metrics_lock:
                if self.metrics["web_attempts"] >= 2:
                    raise ProviderError("search_budget", "本轮检索预算已用完。")
                self.metrics["web_attempts"] += 1
            return self.search.search(scoped)

        return self.cached("web-basic-chunks-v2", scoped, 21600, search)

    def ingest(self, places):
        for place in places:
            if place["id"] not in self.places:
                self.places[place["id"]] = place
                self.add_evidence(
                    place["id"],
                    {
                        "kind": "map_record",
                        "title": place["name"],
                        "url": place["map_url"],
                        "facts": place["facts"],
                    },
                )
            for source in self.research_sources:
                if source_mentions_place(place, source):
                    before = self.evidence_serial
                    self.add_evidence(place["id"], source)
                    if self.evidence_serial != before:
                        self.unsuitable.discard(place["id"])

    def seed_previous(self):
        if not self.plan.reuse_previous or self.context.region != self.previous.get(
            "context", {}
        ).get("region"):
            return []
        cards = self.previous.get("cards", [])
        self.research_sources.extend(
            {key: value for key, value in source.items() if key not in {"id", "place_id"}}
            for card in cards
            for source in card["sources"]
            if source["kind"] in {"web_page", "search_excerpt"}
        )
        self.ingest([card["place"] for card in cards])
        return list(dict.fromkeys(card["place"]["id"] for card in cards))

    def retrieve(self):
        self.stage = "正在并行寻找适合这次想法的去处"
        previous_ids = self.seed_previous()
        indexed = []
        queries = self.plan.map_queries if self.plan.directions else list(
            dict.fromkeys(self.plan.map_queries or self.plan.web_queries or [self.plan.goal]))
        if self.knowledge:
            self.public_groups = [self.knowledge.find(query, region=self.context.region,
                center=self.center, radius=self.context.max_distance_km, limit=12)
                for query in queries]
            # Preserve one slot per query before admitting its second hit. A large
            # single-topic corpus must not crowd out a smaller, relevant direction.
            seen_places = set()
            for offset in range(12):
                for group in self.public_groups:
                    if offset < len(group):
                        entry = group[offset]
                        if entry["place"]["id"] not in seen_places:
                            indexed.append(entry)
                            seen_places.add(entry["place"]["id"])
            indexed = indexed[:12]
            for entry in indexed:
                self.research_sources.extend(entry["sources"])
                self.ingest([entry["place"]])
            self.research_sources = list({s["url"]: s for s in self.research_sources}.values())
            self.metrics["public_place_hits"] = len(indexed)
            self.metrics["public_query_hits"] = {query: len(group)
                for query, group in zip(queries, self.public_groups, strict=True)}
        missing = [i for i, group in enumerate(self.public_groups) if not group]
        query = self.plan.web_queries[0] if self.plan.web_queries else None
        if missing and self.plan.directions:
            # directions carry explicit map/web pairing; never infer the missing
            # need from generic city terms or the number of cached venues.
            query = self.plan.directions[missing[0]].web_query
        # A cold request starts with one search, not three unconditional paid searches.
        tasks = [
            ("web", query)
            for query in [query] if query
            if (len(indexed) < 4 or missing) and not previous_ids and not can_evaluate_map(self)
        ]
        tasks += [("map", query) for query in dict.fromkeys(self.plan.map_queries)]
        results = self.measured(
            "retrieval",
            lambda: self.parallel(
                "retrieval",
                tasks,
                lambda item: (
                    self.web_search(item[1]) if item[0] == "web" else self.map_search(item[1])
                ),
            ),
        )
        fresh = {}
        for (kind, _), values in zip(tasks, results, strict=True):
            if kind == "web":
                for source in values or []:
                    fresh[source["url"]] = source
        # The nomination input is bounded to 18 sources. Newly retrieved evidence
        # for a missing activity must survive that bound instead of being hidden
        # behind a dense cached topic. Source IDs are assigned afterwards.
        self.research_sources = list(fresh.values()) + [
            source for source in self.research_sources if source["url"] not in fresh
        ]
        self.fresh_source_urls.update(fresh)
        for (kind, _), values in zip(tasks, results, strict=True):
            if kind == "map":
                self.ingest(values or [])
        self.map_results = [(query, values or []) for (kind, query), values
                            in zip(tasks, results, strict=True) if kind == "map"]
        self.remember_public()
        if previous_ids and not tasks:
            return previous_ids[:12]
        if len(indexed) >= 4 and not can_evaluate_map(self):
            # These entities are already map-verified. Composition does the semantic ranking,
            # so another model call merely to nominate the same entities is unnecessary.
            self.pending_nomination = any(kind == "web" for kind, _ in tasks)
            self.metrics["nomination_skipped"] = not self.pending_nomination
            return [entry["place"]["id"] for entry in indexed][:12]
        if not self.places and not self.research_sources:
            return []
        if can_evaluate_map(self):
            # Evaluate current per-query retrievals alongside public knowledge.
            # A dense cached topic must not hide freshly retrieved alternatives.
            fresh_groups = dict(self.map_results)
            groups = []
            for index, query in enumerate(queries):
                public = ([entry["place"] for entry in self.public_groups[index]]
                          if index < len(self.public_groups) else [])
                groups.append((query, [*fresh_groups.get(query, []), *public]))
            candidates = select_retrieved_places(groups) if any(values for _, values in groups) else select_places(
                list(self.places.values()), self.selection_queries(), limit=12)
            self.nominated_ids = [p["id"] for p in candidates]
            return self.nominated_ids
        return self.nominate()

    def remember_public(self):
        if self.knowledge:
            for place in self.places.values():
                self.knowledge.remember(place, list(self.evidence.values()))

    def nominate(self):
        self.stage = "正在从资料中挑选具体去处"
        selected_sources = select_sources(self.research_sources, self.selection_queries(),
                                          recent_urls=self.fresh_source_urls)
        visible_sources = {id(s) for s in selected_sources}
        source_ids = {f"s{i}": source for i, source in enumerate(self.research_sources, 1)
                      if id(source) in visible_sources}
        sources = [
            {"source_id": key, "title": s.get("title", ""), "excerpt": s.get("excerpt", "")[:800]}
            for key, s in source_ids.items()
        ]
        selected_places = select_places(list(self.places.values()), self.selection_queries())
        places = [
            {key: p[key] for key in ("id", "name", "city", "address", "map_type")}
            for p in selected_places
        ]
        context = self.request_context() | {
            "retrieval_hypotheses": [d.model_dump() for d in self.plan.directions],
        }
        selection_key = [
            getattr(self.model, "version", "test"),
            self.turns,
            self.body.message,
            context,
            sources,
            places,
        ]
        selected = VenueSelection.model_validate(
            self.cached(
                "nomination-v8",
                selection_key,
                300,
                lambda: self.model_call(
                    "nomination",
                    lambda: self.model.nominate(
                        self.turns, self.body.message, context, sources, places
                    ),
                ).model_dump(mode="json"),
            )
        )
        self.evidence_query = selected.evidence_query
        self.record_evidence_needs(selected.evidence_needs, [p["id"] for p in selected_places])
        # Check BOTH name and ID. A plausible name with another venue's ID is not a match.
        for lead in selected.venues:
            if lead.place_id and (
                lead.place_id not in {p["id"] for p in selected_places}
                or (lead.name and not self.same_venue_name(lead.name, self.places[lead.place_id]["name"]))
            ):
                lead.place_id = None
            if lead.place_id and not lead.name:
                lead.name = self.places[lead.place_id]["name"]
            if not lead.name:
                continue
            if not lead.source_urls and not lead.source_ids:
                lead.source_urls = [
                    s["url"]
                    for s in self.research_sources
                    if source_mentions_place(
                        {"name": lead.name, "city": self.context.region or ""}, s
                    )
                ][:4]
        # A model can propose names, never arbitrary coordinates or fabricated place IDs.
        leads = [lead for lead in selected.venues if not lead.place_id and lead.name]
        for lead in leads:
            if lead.source_ids and all(key in source_ids for key in lead.source_ids):
                lead.source_urls = [source_ids[key]["url"] for key in lead.source_ids]
        known_urls = {source["url"] for source in self.research_sources}
        leads = [lead for lead in leads if lead.source_urls and set(lead.source_urls) <= known_urls]
        found = self.measured(
            "map_verification",
            lambda: self.parallel(
                "map_verification", leads, lambda lead: self.map_search(lead.name)
            ),
        )
        lead_ids = {}
        for lead, values in zip(leads, found, strict=True):
            name = re.sub(r"\s", "", lead.name).split("(", 1)[0].split("（", 1)[0]
            matches = [
                place
                for place in values or []
                if len(name) >= 2 and name in re.sub(r"\s", "", place["name"])
            ]
            self.ingest(matches)
            lead_ids[lead.name] = [place["id"] for place in matches[:1]]
        ids = []
        for lead in selected.venues:
            if lead.place_id:
                if lead.place_id in self.places:
                    ids.append(lead.place_id)
                else:
                    self.errors.append({"tool": "nomination", "code": "unknown_place"})
            else:
                ids.extend(lead_ids.get(lead.name, []))
        self.remember_public()
        published = {c["place"]["id"] for c in self.cards}
        self.nominated_ids = [key for key in dict.fromkeys(ids)
                              if key not in published and key not in self.structural_rejections
                              and key not in self.unsuitable][:12]
        self.ensure_core_evidence(self.nominated_ids)
        return self.nominated_ids

    def selection_queries(self):
        queries = [r.text for r in self.plan.requirements
                   if r.scope == "place" and r.importance == "required"]
        queries += self.plan.map_queries + self.plan.web_queries
        queries += [d.map_query for d in self.plan.directions]
        region = self.context.region
        return [q.replace(region, " ").strip() if region else q for q in queries]

    def request_context(self):
        return {
            **self.context.model_dump(mode="json"),
            "user_request": {
                "messages": [t["content"] for t in self.turns if t["role"] == "user"],
                "criteria": criterion_view(self.plan.requirements),
                "requirement_groups": [g.model_dump() for g in self.plan.requirement_groups],
            },
            "allow_business_inference": bool(self.reviewer),
        }

    def record_evidence_needs(self, needs, eligible_ids):
        eligible = set(eligible_ids) & self.places.keys()
        existing = {(n.place_id, n.requirement if n.requirement else n.query) for n in self.evidence_needs}
        for value in needs:
            need = EvidenceNeed.model_validate(value)
            key = (need.place_id, need.requirement if need.requirement else need.query)
            if need.requirement and need.requirement > len(self.plan.requirements):
                continue
            if need.place_id in eligible and key not in existing:
                self.evidence_needs.append(need)
                existing.add(key)
            elif need.place_id in eligible and need.date_sensitive:
                for previous in self.evidence_needs:
                    if (previous.place_id, previous.requirement if previous.requirement else previous.query) == key:
                        previous.date_sensitive = True

    def pending_evidence_needs(self):
        published = {c["place"]["id"] for c in self.cards}
        return [n for n in self.evidence_needs if n.place_id not in published
                and n.place_id not in self.structural_rejections
                and n.place_id not in self.unsuitable
                and self.need_query(n) not in self.web_seen
                and (not self.plan.requirements or (
                    n.requirement is not None
                    and self.plan.requirements[n.requirement - 1].scope == "place"
                    and self.plan.requirements[n.requirement - 1].importance == "required"))]

    def need_query(self, need):
        name = self.places[need.place_id]["name"]
        dates = ""
        if need.date_sensitive:
            dates = " ".join(dict.fromkeys(str(value) for value in
                (self.context.start_date, self.context.end_date) if value))
            dates = (" " + dates) if dates else ""
        if need.requirement is not None:
            # A model may mislabel its free-form query. Execute the bound user
            # condition, not another model paraphrase that can reintroduce a preference.
            return name + " " + self.plan.requirements[need.requirement - 1].text + dates
        return (need.query if need.query.startswith(name) else name + " " + need.query) + dates

    def ensure_core_evidence(self, ids, *, force=False):
        needs = []
        for key in ids:
            if key in self.structural_rejections or key in self.unsuitable:
                continue
            if not force and any(e["place_id"] == key and e["kind"] in {"web_page", "search_excerpt"}
                   for e in self.evidence.values()):
                continue
            for i, requirement in enumerate(self.plan.requirements, 1):
                if (requirement.role == "condition" and requirement.scope == "place"
                        and requirement.importance == "required" and not requirement.map_field):
                    needs.append(EvidenceNeed(place_id=key, query=requirement.text + " 公开介绍", requirement=i))
        self.record_evidence_needs(needs, ids)

    @staticmethod
    def same_venue_name(requested, actual):
        name = re.sub(r"\s", "", requested).split("(", 1)[0].split("（", 1)[0]
        return len(name) >= 2 and name in re.sub(r"\s", "", actual)

    def facts(self, ids):
        self.stage = "正在批量核实到达路线和天气"
        tasks = []
        for key in ids:
            if self.center:
                tasks.append(("route", key))
            if self.context.start_date:
                tasks.append(("weather", key))

        def fetch(item):
            kind, key = item
            place = self.places[key]
            if kind == "route":
                cache_key = [
                    key,
                    self.center.model_dump(),
                    arrival_coordinate(place).model_dump(),
                    self.context.travel_mode,
                ]
                return self.cached(
                    "route-v1",
                    cache_key,
                    300,
                    lambda: self.map_request(
                        lambda: self.maps.route(self.center, place, self.context.travel_mode)
                    ),
                )
            point = Coordinate(**place["coordinate"])
            cache_key = [
                point.model_dump(),
                str(self.context.start_date),
                str(self.context.end_date),
            ]
            return self.cached(
                "weather-v1",
                cache_key,
                600,
                lambda: [
                    day.model_dump(mode="json")
                    for day in self.weather.daily(
                        point, self.context.start_date, self.context.end_date
                    )
                ],
            )

        data = self.measured("facts", lambda: self.parallel("facts", tasks, fetch))
        for (kind, key), value in zip(tasks, data, strict=True):
            value = value if value is not None else {"unavailable": True}
            (self.routes if kind == "route" else self.forecasts)[key] = value
            self.add_evidence(
                key,
                {"kind": "measure_routes" if kind == "route" else "check_weather", "facts": value},
            )
        valid = []
        for key in ids:
            route = self.routes.get(key)
            if self.context.max_distance_km is not None and (
                not route
                or route.get("unavailable")
                or route["distance_km"] > self.context.max_distance_km
            ):
                continue
            valid.append(key)
        return valid

    def review_cards(self, cards):
        data = [self.review_inputs.get(c["place"]["id"], c) for c in cards]
        result = self.model_call("review", lambda: self.reviewer(model_tool_view(data)))
        revisions = validated_revisions(result, data)
        self.record_collection_review(result, {c["place"]["id"] for c in self.cards})
        self.evidence_query = result.evidence_query
        self.record_evidence_needs(result.evidence_needs, [c["place"]["id"] for c in cards])
        covered = set()
        for coverage in result.covered_directions:
            if coverage.direction > len(self.plan.directions) or not set(coverage.place_ids) <= set(result.approved_ids):
                raise ValueError("体验覆盖引用了未通过的地点或未知方向。")
            covered.add(coverage.direction)
        self.covered_directions.update(covered)
        for card in cards:
            if card["place"]["id"] not in result.approved_ids:
                continue
            direction = next((c.direction for c in result.covered_directions
                if card["place"]["id"] in c.place_ids), None)
            if direction:
                # Group by this request's verified activity, not arbitrary
                # promotional names or the retired fixed scenery categories.
                card["experience"] = self.plan.directions[direction - 1].experience
            selected = self.review_inputs.get(card["place"]["id"], {}).get("sources", [])
            if (revision := revisions.get(card["place"]["id"])):
                additional = {s["evidence_id"] for s in selected if s["id"] in revision.evidence_ids}
                existing = {s["id"] for s in card["sources"]}
                card["sources"] += [self.evidence[key] for key in additional - existing]
            card["sources"] = cited_sources(card["sources"], selected)
        return result

    def record_collection_review(self, result, reviewed_previous):
        current = {c["place"]["id"] for c in self.cards}
        valid = collection_assessments(
            criterion_view(self.plan.requirements), result.collection_assessments,
            set(reviewed_previous) | set(result.approved_ids),
        )
        # A parallel worker may have reviewed an older prefix. Its list-level
        # decision cannot certify the newer list, even if its individual cards fit.
        self.collection_assessments = valid if set(reviewed_previous) == current else {}

    def collection_gaps(self):
        return [i for i, requirement in enumerate(self.plan.requirements, 1)
                if requirement.scope == "collection" and requirement.importance == "required"
                and not self.collection_assessments.get(i, {}).get("satisfied")]

    def finalize_collection(self):
        evaluate = getattr(self.model, "assess_collection", None)
        if not (self.cards and getattr(self.model, "source_first", False)
                and callable(evaluate) and self.collection_gaps()):
            return
        with self.lock:
            cards = copy.deepcopy(self.cards)
        expected = [c["place"]["id"] for c in cards]
        result = self.model_call("collection", lambda: evaluate(
            self.turns, self.request_context(), cards))
        valid = collection_assessments(criterion_view(self.plan.requirements),
                                       result.collection_assessments, set(expected))
        self.check()
        with self.lock:
            if expected != [c["place"]["id"] for c in self.cards]:
                raise ValueError("整组结果已变化，不能套用旧判断。")
            self.collection_assessments = valid

    def review_context(self):
        return {**self.request_context(),
            "requested_directions": [{"index": i, **d.model_dump()} for i, d in enumerate(self.plan.directions, 1)],
            "covered_direction_indices": sorted(self.covered_directions),
            "already_published": [{"id": c["place"]["id"], "name": c["place"]["name"],
                "experience": c["experience"]} for c in self.cards]}

    def plan_context(self, plan):
        # Nulls produced for optional schema fields are not implicit delete commands.
        updates = plan.context.model_dump(exclude_none=True, exclude_unset=True)
        updates.pop("travel_mode_quote", None)
        original = "\n".join(t["content"] for t in self.turns if t["role"] == "user")
        requirement_groups(criterion_view(plan.requirements), plan.requirement_groups, original)
        if plan.collection_quote and (
            plan.collection_quote not in original
            or not any(r.scope == "collection" for r in plan.requirements)
        ):
            raise ValueError("整组要求已表达，必须保留为scope=collection项目并引用原话，不能遗漏。")
        if plan.temporal:
            resolved = temporal_updates(plan.temporal, self.context, original,
                datetime.now(timezone(timedelta(hours=8))).date())
            if any(updates.get(key) is not None and updates[key] != resolved[key]
                   for key in ("start_date", "end_date")):
                raise ValueError("时间意图与context日期不一致，不能忽略或重复猜测。")
            updates.update(resolved)
        if (
            "travel_mode" in updates
            and updates["travel_mode"] != self.context.travel_mode
            and (not plan.travel_mode_quote or plan.travel_mode_quote not in original)
        ):
            updates.pop("travel_mode")
        # A delete of an already absent optional value is a no-op, not a user
        # intent requiring evidence. Keep evidence checks for every real delete
        # and for deletes that would override a value set in the same patch.
        effective_clears = [name for name in plan.clear_fields
                            if getattr(self.context, name) is not None or updates.get(name) is not None]
        if effective_clears:
            if not plan.clear_quote or plan.clear_quote not in original:
                raise ValueError("清空条件需要明确原文依据。")
            updates.update(dict.fromkeys(effective_clears))
        for i, requirement in enumerate(plan.requirements):
            if requirement.quote not in original:
                raise ValueError(f"requirements[{i}].quote需要逐字引用用户原文。")
        if plan.nearby_quote:
            if plan.nearby_quote not in original:
                raise ValueError("nearby_quote需要逐字引用用户原文，仅指定城市不等于请求附近。")
            # Nearby uses the map search's local retrieval radius. Only an
            # explicit user distance becomes a hard measured-route constraint.
        chosen = self.body.location_details if self.body.use_location else None
        if chosen and chosen.source == 'selected':
            updates.update(origin=chosen.name, origin_quote=None)
        elif chosen and chosen.replace_origin:
            updates.update(origin=None, origin_quote=None)
        value = SearchContext.model_validate(updates)
        self.validate_context_evidence(value)
        return value

    def configure_plan(self):
        value = self.plan_context(self.plan)
        updates = value.model_dump(exclude_unset=True)
        if (self.location is not None or not self.body.use_location) and not updates.get("origin", self.context.origin):
            self.center = None
            self.center_name = None
        return self.configure(value)

    def load_plan(self, context, previous_cards):
        if (self.body.location_details or not self.body.use_location) and self.previous.get('_location_plan'):
            # The owned prior search supplies its intent; an explicit location
            # button does not need another model to reinterpret the same wish.
            plan = RetrievalPlan.model_validate(self.previous['_location_plan'])
            plan.context = SearchContext.model_validate(self.context.model_dump())
            plan.clear_fields = []
            return plan.model_dump(mode='json')
        plan = self.model_call("planning", lambda: self.model.plan(
            self.turns, context, self.location is not None, previous_cards,
            {**self.body.view.model_dump(), "recent_conversation": [
                m.model_dump() for m in self.body.conversation]},
        ))
        original = "\n".join(t["content"] for t in self.turns if t["role"] == "user")
        if plan.intent == "search":
            try:
                plan = compile_intent(plan, original)
                self.plan_context(plan)
            except ValueError as error:
                repair = getattr(self.model, "repair_plan", None)
                if repair is None:
                    raise
                violation = str(error)
                plan = self.model_call("planning_repair", lambda: repair(
                    self.turns, context, self.location is not None,
                    plan.model_dump(mode="json", exclude_unset=True), violation,
                ))
                self.check()
                if plan.intent != "search":
                    raise ValueError("条件纠正不能改为执行业务。") from None
                plan = compile_intent(plan, original)
                self.plan_context(plan)
                with self.metrics_lock:
                    self.metrics["plan_repairs"] = self.metrics.get("plan_repairs", 0) + 1
            # Only complete, validated updates leave intake. This permits native
            # sparse endpoints without weakening the retrieval/public contracts.
            canonical = self.plan_context(plan)
            plan.context = type(plan.context).model_validate(canonical.model_dump(exclude_unset=True))
        self.check()
        return plan.model_dump(mode="json", exclude_unset=True)

    def compose(self, ids):
        self.check()
        if getattr(self.model, "source_first", False):
            return self.assess_candidates(ids)
        if self.reviewer is None and any(r.role == "goal" for r in self.plan.requirements):
            raise ValueError("活动目标需要对照完整原话作独立适配审查。")
        self.stage = "正在为这批去处整理具体理由"
        passages, candidates = candidate_view(self, ids)
        if not candidates:
            return 0
        context = self.request_context() | {
            "reference_date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
            "requirements": criterion_view(self.plan.requirements),
        }
        proposed = self.model_call(
            "composition",
            lambda: self.model.compose(
                self.turns,
                self.body.message,
                context,
                model_tool_view(candidates),
            ),
        )
        self.check()
        self.unsuitable.update(unsuitable_ids(proposed, ids, passages))
        self.record_evidence_needs(proposed.evidence_needs, ids)
        published = {c["place"]["id"] for c in self.cards}
        accepted = []
        for card in proposed.cards:
            refs = referenced_passages(card, passages)
            supports = getattr(card, "requirement_support", [])
            coverage = supported_criteria(context["requirements"], supports, passages, card.place_id,
                                          allow_business_inference=bool(self.reviewer),
                                          cited_ids=card.evidence_ids)
            if (
                card.place_id not in ids
                or card.place_id in published
                or any(not s or s["place_id"] != card.place_id for s in refs)
                or coverage is None
            ):
                self.reject_card("invalid_evidence")
                if card.place_id in ids:
                    self.structural_rejections.add(card.place_id)
                continue
            if not entity_supported(self.places[card.place_id], refs):
                self.reject_card("missing_entity_reference")
                continue
            # Map back to actual stored sources only after each passage has been checked.
            base_ids = list(dict.fromkeys(s["evidence_id"] for s in refs))
            accepted.append(
                ProposedCard(
                    place_id=card.place_id,
                    experience=card.experience,
                    reason=card.reason,
                    evidence_ids=base_ids,
                )
            )
            published.add(card.place_id)
            self.review_inputs[card.place_id] = {
                "place": self.places[card.place_id],
                "experience": card.experience,
                "reason": card.reason,
                "sources": [p for p in passages.values() if p["place_id"] == card.place_id],
                **coverage,
                "route": self.routes.get(card.place_id),
                "weather": self.forecasts.get(card.place_id),
            }
        before = len(self.cards)
        if accepted:
            self.act("publish_batch", Publish(cards=accepted))
        if len(self.cards) == before:
            self.ensure_core_evidence(ids, force=True)
        return len(self.cards) - before

    def assess_candidates(self, ids):
        from roambot.services.discovery_batches import BatchWorker, freeze_batch

        if self.reviewer is None:
            raise ValueError("直接核验必须配置独立证据判断与最终写作。")
        self.stage = "正在核对本批去处并整理推荐理由"
        revision = getattr(self, "revision", 1)
        batch = freeze_batch(self, 0, ids, revision)
        worker = BatchWorker(self.model,
            lambda conversation, context, cards: self.reviewer(cards),
            call=lambda stage, invoke, sequence: self.model_call(stage, invoke),
            cache=self.cache, check=self.check)
        draft = worker.compose(batch)
        decision = worker.review(batch, draft)
        return self.commit_reviewed_batch(batch, draft, decision, revision=revision)["published"]

    def reject_card(self, code):
        self.metrics["rejected_cards"] += 1
        self.errors.append({"tool": "composition", "code": code})

    def supplement(self):
        if self.places and self.places.keys() <= (self.structural_rejections | self.unsuitable):
            return []  # Protocol failures are not missing facts; do not buy more evidence.
        missing_queries = [d.web_query for i, d in enumerate(self.plan.directions, 1)
            if i not in self.covered_directions and d.web_query not in self.web_seen]
        pending = self.pending_evidence_needs()
        query = next((self.need_query(n) for n in pending), None) or (self.evidence_query if self.evidence_query not in self.web_seen and not self.plan.requirements else None) or next(iter(missing_queries), None) or next(
            (q for q in self.plan.web_queries if q not in self.web_seen), None
        )
        if not query or query in self.web_seen or self.metrics["web_attempts"] >= 2:
            return []
        self.stage = "正在补查缺少的地点依据"
        found = self.web_search(query)
        known = {s["url"] for s in self.research_sources}
        additional = [s for s in found if s["url"] not in known]
        if not additional:
            return []
        self.research_sources = additional + self.research_sources
        self.fresh_source_urls.update(s["url"] for s in additional)
        self.ingest(list(self.places.values()))
        published = {c["place"]["id"] for c in self.cards}
        known = [key for key in self.nominated_ids if key not in published
                 and key not in self.structural_rejections and any(
            e["place_id"] == key and e["kind"] in {"web_page", "search_excerpt"}
            for e in self.evidence.values())]
        known = [key for key in known if key not in self.unsuitable]
        if known:
            return known
        return self.nominate()

    def process_candidates(self, ids):
        direct = bool(getattr(self.model, "source_first", False))
        first = assessment_batch_size(len(ids), first=True) if direct else initial_batch_size(len(ids))
        valid = self.facts(ids[:first])
        if valid:
            self.process_batch(valid)
        remaining = ids[first:]
        if not self.cards and self.pending_evidence_needs():
            # Resolve a promising first batch's concrete gap before spending
            # model rounds on the entire tail. The shared search budget applies.
            extra = self.supplement()
            self.process_supplement(extra)
            remaining = [key for key in remaining if key not in set(extra)]
        if self.pending_nomination:
            nominees = self.nominate()
            shown = {c["place"]["id"] for c in self.cards}
            remaining = [key for key in dict.fromkeys(nominees + remaining)
                         if key not in shown][:12-len(shown)]
        size = assessment_batch_size(6) if direct else 6
        for start in range(0, len(remaining), size):
            pending = [key for key in remaining[start:start + size]
                       if key not in self.structural_rejections and key not in self.unsuitable]
            valid = self.facts(pending)
            if valid:
                self.process_batch(valid)

    def process_batch(self, ids):
        try:
            return self.compose(ids)
        except ProviderError as error:
            if not getattr(self.model, "source_first", False) or error.code not in {"timeout", "bad_response"}:
                raise
            # A failed batch is still reported as incomplete, but must not erase
            # earlier cards or prevent independent later candidates being assessed.
            self.errors.append({"tool": "assessment_batch", "code": error.code})
            return 0

    def process_supplement(self, ids):
        size = assessment_batch_size(4) if getattr(self.model, "source_first", False) else 4
        for start in range(0, len(ids), size):
            valid = self.facts(ids[start:start + size])
            if valid:
                self.process_batch(valid)

    def run(self):
        try:
            self.stage = "正在理解这次想法并安排检索"
            context = self.context.model_dump(mode="json")
            previous_cards = [
                {"name": c["place"]["name"], "id": c["place"]["id"]}
                for c in self.previous.get("cards", [])
            ]
            today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            plan_key = [
                getattr(self.model, "version", "test"),
                today,
                self.turns,
                context,
                self.location.model_dump() if self.location else None,
                previous_cards,
                self.body.view.model_dump(),
                [m.model_dump() for m in self.body.conversation],
            ]
            self.plan = RetrievalPlan.model_validate(
                self.cached(
                    "retrieval-plan-v23",
                    plan_key,
                    300,
                    lambda: self.load_plan(context, previous_cards),
                )
            )
            self.check()
            if self.plan.intent == "business":
                if self.plan.business_plan:
                    proposed = self.plan.business_plan
                    if bool(proposed.question) == bool(proposed.actions):
                        raise ValueError("操作须为完整动作或单独追问。")
                    for action in proposed.actions:
                        if action.tool not in INTAKE_TOOLS:
                            raise ValueError("该操作需要完整业务规划。")
                        action.validated_arguments()
                # No context changes, geocoding, retrieval or fabricated completion.
                # The client hands the original message to the authorized executor.
                self.status = "completed"
                self.reply = ""
                return
            if self.plan.directions:
                core = list(dict.fromkeys(d.map_query for d in self.plan.directions))
                preferences = [d.preference_query for d in self.plan.directions
                               if d.preference_query and d.preference_query not in core]
                self.plan.map_queries = core + list(dict.fromkeys(preferences))[:max(0, 3 - len(core))]
                self.plan.web_queries = [d.web_query for d in self.plan.directions]
            self.measured("context", self.configure_plan)
            if not self.center and (
                not self.context.region or self.context.max_distance_km is not None
            ):
                self.request_location = True
                self.reply = "想在哪附近看看？可以使用当前位置，也可以直接说地区。"
                self.status = "completed"
                return
            ids = self.retrieve()
            self.process_candidates(ids)
            self.finalize_collection()
            for _ in range(2):
                if self.metrics["web_attempts"] >= 2 or not (
                    not self.cards
                    or self.collection_gaps()
                    or (not self.plan.requirements
                        and not getattr(self.model, "source_first", False)
                        and len(self.covered_directions) < len(self.plan.directions))
                    or (
                        not self.plan.requirements
                        and len({c["experience"] for c in self.cards}) < 2
                    )
                ):
                    break
                extra = self.supplement()
                self.process_supplement(extra)
                if extra:
                    self.finalize_collection()
            self.check()
            missing = [i for i in range(1, len(self.plan.directions) + 1) if i not in self.covered_directions]
            self.metrics["uncovered_direction_indices"] = missing
            self.metrics["unmet_collection_requirements"] = self.collection_gaps()
            self.status = (
                "completed"
                if (self.cards and not self.errors and (not missing or self.plan.requirements
                    or (getattr(self.model, "source_first", False)
                        and len({c["experience"] for c in self.cards}) >= 2))
                    and not self.collection_gaps())
                else "partial"
                if self.cards
                else "failed"
            )
            self.reply = "已找到这些去处。" if self.cards else "这轮尚未找到依据充分的去处。"
        except Stopped as error:
            if str(error) and not self.cancelled.is_set():
                self.errors.append({"tool": "workflow", "code": str(error)})
            self.status = (
                "cancelled" if self.cancelled.is_set() else "partial" if self.cards else "failed"
            )
        except (ProviderError, ValueError, KeyError) as error:
            logger.warning("discovery_workflow_failed stage=%s error_type=%s code=%s",
                self.stage, type(error).__name__, getattr(error, "code", "invalid_result"))
            self.errors.append(
                {"tool": "workflow", "code": getattr(error, "code", "invalid_result")}
            )
            self.status = "partial" if self.cards else "failed"
        except Exception as error:
            logger.warning("discovery_workflow_failed stage=%s error_type=%s code=unexpected_error",
                self.stage, type(error).__name__)
            self.errors.append({"tool": "workflow", "code": "unexpected_error"})
            self.status = "partial" if self.cards else "failed"
        finally:
            self.stage = ""
            if not self.reply and not (self.plan and self.plan.intent == "business"):
                self.reply = "已保留找到的去处。" if self.cards else "这轮查询尚未完成。"
