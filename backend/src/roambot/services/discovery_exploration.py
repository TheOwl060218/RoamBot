"""Conversation-local exploration of qualified, real map objects; no provider calls here."""

import copy
import math
import statistics
import time
from datetime import datetime, timedelta, timezone

POOL_TTL_SECONDS = 600  # Same freshness window as the existing weather facts cache.


def point(place):
    value = place.get("coordinate") or {}
    return float(value.get("longitude", 0)), float(value.get("latitude", 0))


def distance(left, right):
    a, b = point(left), point(right)
    lat = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * math.cos(lat), a[1] - b[1])


def seen_places(previous):
    unique = {p["id"]: p for p in previous.get("exploration_state", {}).get("seen", [])}
    for card in previous.get("cards", []):
        p = card["place"]
        unique[p["id"]] = {
            key: copy.deepcopy(p.get(key)) for key in ("id", "name", "city", "coordinate", "facts")
        }
    return list(unique.values())


def other_area(place, seen):
    if not seen:
        return True
    district = (place.get("facts") or {}).get("district")
    districts = {(p.get("facts") or {}).get("district") for p in seen}
    if district and district not in districts:
        return True
    # Neighbouring POIs are not another area merely because they lie a few
    # metres outside the previous bounding box. This is a novelty preference,
    # never an expansion of the user's allowed travel distance.
    gaps = (
        [min(distance(p, q) for j, q in enumerate(seen) if i != j) for i, p in enumerate(seen)]
        if len(seen) > 1
        else []
    )
    neighbourhood = max(statistics.median(gaps) if gaps else 0, 1 / 111)
    return min(distance(place, p) for p in seen) > neighbourhood


def spatial_order(cards, seen=(), limit=12):
    """Soft relevance/diversity tradeoff inside an already qualified candidate set."""
    remaining = list(cards)
    ranks = {id(card): i for i, card in enumerate(remaining)}
    places = [card["place"] for card in remaining]
    gaps = [
        distance(a, b) for i, a in enumerate(places) for b in places[i + 1 :] if distance(a, b) > 0
    ]
    scale = statistics.median(gaps) if gaps else 0
    chosen = []
    while remaining and len(chosen) < limit:

        def score(card):
            relevance = 1 - ranks[id(card)] / max(1, len(cards))
            reference = [c["place"] for c in chosen] + list(seen)
            redundancy = (
                max((math.exp(-distance(card["place"], p) / scale) for p in reference), default=0)
                if scale
                else 0
            )
            return relevance - 0.35 * redundancy

        best = max(remaining, key=score)
        remaining.remove(best)
        chosen.append(best)
    return chosen


class ExplorationMixin:
    def setup_exploration(self):
        self.explore_mode = self.body.explore_mode
        self.reserve_cards = []
        self.pool_created_at = time.time()
        self.used_reserve = False
        self.pinned_cards = []
        self.update_exploration_context()

    def update_exploration_context(self):
        seen = seen_places(self.previous) if self.explore_mode else []
        self.model.exploration_context = {
            "mode": self.explore_mode,
            "already_shown": [
                {
                    "id": p["id"],
                    "name": p.get("name"),
                    "district": (p.get("facts") or {}).get("district"),
                }
                for p in seen
            ],
        }
        if self.explore_mode:
            by_id = {c["place"]["id"]: c for c in self.previous.get("cards", [])}
            if any(key not in by_id for key in self.body.view.selected_ids):
                raise ValueError("已选地点不属于当前推荐。")
            self.pinned_cards = [copy.deepcopy(by_id[key]) for key in self.body.view.selected_ids]

    def load_plan(self, context, previous_cards):
        if self.body.explore_mode:
            plan = copy.deepcopy(self.previous.get("_explore_plan"))
            if not plan:
                plan = {
                    "context": context,
                    "goal": self.search_request or self.body.message,
                    "display_title": self.previous.get("display_title"),
                    "search_scope": self.previous.get("search_scope"),
                    "web_queries": [self.search_request or self.body.message],
                }
            plan["explore_mode"] = self.body.explore_mode
            plan.update(
                context=context,
                temporal=None,
                clear_fields=[],
                clear_quote=None,
                nearby_quote=None,
                travel_mode_quote=None,
                request_location=False,
            )
            self.update_exploration_context()
            return plan
        plan = super().load_plan(context, previous_cards)
        self.explore_mode = plan.get("explore_mode") if self.previous.get("cards") else None
        self.update_exploration_context()
        return plan

    def use_exploration_reserve(self):
        if not self.explore_mode:
            return False
        if self.body.location and self.body.location.model_dump() != self.previous.get(
            "_location_input"
        ):
            return False
        if (
            self.body.location_details
            and self.body.location_details.model_dump() != self.previous.get("_location_metadata")
        ):
            return False
        from roambot.domain.discovery import SearchContext

        updates = self.plan.context.model_dump(exclude_unset=True, exclude_none=True)
        if (
            self.plan.clear_fields
            or SearchContext.model_validate(self.context.model_dump() | updates) != self.context
        ):
            self.explore_mode = None
            self.update_exploration_context()
            return False
        state = self.previous.get("exploration_state") or {}
        if (
            self.context.start_date
            and self.context.start_date < datetime.now(timezone(timedelta(hours=8))).date()
        ):
            raise ValueError("原出游日期已过，请先修改日期。")
        if time.time() - state.get("created_at", 0) >= POOL_TTL_SECONDS:
            return False
        seen = seen_places(self.previous)
        shown = {p["id"] for p in seen}
        available = [
            copy.deepcopy(c)
            for c in state.get("reserve", [])
            if c["place"]["id"] not in shown
            and (self.explore_mode != "area" or other_area(c["place"], seen))
        ]
        if not available:
            return False
        chosen = spatial_order(available, seen, 12)
        used = {c["place"]["id"] for c in chosen}
        self.pool_created_at = state["created_at"]
        self.reserve_cards = [
            copy.deepcopy(c)
            for c in state.get("reserve", [])
            if c["place"]["id"] not in shown | used
        ]
        self.used_reserve = True
        self._append_cards(chosen, [], reviewed=False)
        self.status = "completed"
        return True

    def prepare_publication(self, primary, reserve):
        qualified = primary + reserve
        seen = seen_places(self.previous) if self.explore_mode else []
        chosen = spatial_order(qualified, seen, len(primary))
        ids = {c["place"]["id"] for c in chosen}
        self.reserve_cards.extend(c for c in qualified if c["place"]["id"] not in ids)
        return chosen

    def _append_cards(self, pending, rejected, *, reviewed):
        with self.lock:
            self.check()
            if pending and self.pinned_cards and not self.cards:
                self.cards.extend(copy.deepcopy(self.pinned_cards))
            return super()._append_cards(pending, rejected, reviewed=reviewed)

    def snapshot(self):
        value = super().snapshot()
        same_region = self.context.region and self.context.region == self.previous.get(
            "context", {}
        ).get("region")
        seen = {
            p["id"]: p
            for p in (seen_places(self.previous) if self.explore_mode or same_region else [])
        }
        for card in self.cards:
            p = card["place"]
            seen[p["id"]] = {
                key: copy.deepcopy(p.get(key))
                for key in ("id", "name", "city", "coordinate", "facts")
            }
        value["exploration_state"] = {
            "seen": list(seen.values())[-1536:],
            "reserve": copy.deepcopy(self.reserve_cards),
            "created_at": self.pool_created_at,
        }
        pinned = {c["place"]["id"] for c in self.pinned_cards}
        value["exploration"] = {
            "mode": self.explore_mode,
            "remaining": len(self.reserve_cards),
            "seen_count": len(seen),
            "new_count": sum(c["place"]["id"] not in pinned for c in self.cards),
            "used_reserve": self.used_reserve,
        }
        if (
            self.explore_mode
            and not self.cards
            and self.status in {"completed", "partial", "failed"}
        ):
            value["reply"] = (
                "暂未找到其他区域的合适去处，当前推荐已保留。"
                if self.explore_mode == "area"
                else "暂未找到更多合适去处，当前推荐已保留。"
            )
        return value
