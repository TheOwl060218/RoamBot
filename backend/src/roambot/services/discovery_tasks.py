"""Bounded alternative: task intake, real retrieval, then one selection per batch.

This deliberately does not invoke the observation/approval/collection pipeline.
It reuses context validation, provider adapters, ownership and publication storage.
"""

import copy
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import Field

from roambot.domain.business_tools import BusinessPlan, INTAKE_TOOLS, TOOL_CATALOG
from roambot.domain.discovery import (
    Contract, ProposedCard, RetrievalDirection, RetrievalPlan, SearchContextUpdate, TemporalIntent,
)
from roambot.providers.discovery_workflow import structured_call
from roambot.providers.discovery_usage import capture_model_usage
from roambot.providers.protocols import ProviderError
from roambot.providers.discovery import source_mentions_place
from roambot.services.discovery_execution import ExecutionBudget, ExecutionStopped, ExecutionTrace, ModelGate
from roambot.services.discovery_grounding import map_fact_passages, passage_view
from roambot.services.discovery_selection import select_retrieved_places
from roambot.services.discovery_task_evidence import selection_facts, task_model_facts

logger = logging.getLogger(__name__)
from roambot.services.discovery_workflow import DiscoveryWorkflow, Stopped


class TaskDirection(Contract):
    experience: str = Field(min_length=1, max_length=30)
    keyword: str = Field(min_length=1, max_length=80)


class IntakeContext(Contract):
    intent: Literal["search", "business"]
    business_plan: BusinessPlan | None = None
    context: SearchContextUpdate
    temporal: TemporalIntent | None
    nearby_quote: str | None = Field(default=None, max_length=200)
    clear_fields: list[Literal["origin", "region", "max_distance_km", "start_date", "end_date"]] = Field(default_factory=list, max_length=5)
    clear_quote: str | None = Field(default=None, max_length=200)
    travel_mode_quote: str | None = Field(default=None, max_length=200)


class TaskIntake(IntakeContext):
    directions: list[TaskDirection] = Field(max_length=5)
    research_query: str | None = Field(default=None, max_length=160)


class TaskSelection(Contract):
    cards: list[ProposedCard] = Field(default_factory=list, max_length=6)
    research_query: str | None = Field(default=None, max_length=160)


class DiscoveryTaskModel:
    def __init__(self, provider):
        self.provider = provider
        self.version = provider._model + ":task-intake-v3"

    def plan(self, conversation, context, location_available, previous_cards, view=None):
        today = datetime.now(timezone(timedelta(hours=8))).date()
        value = structured_call(self.provider, "plan_task", TaskIntake,
            "理解完整原话及改口。查找去处为search；页面/收藏/比较/计划/邀请/投票/历史等操作为business，"
            "混合业务也交business。business不检索，directions=[]、context={}、temporal=null。"
            "仅当完整请求的全部操作都属于intake_tools时，填写business_plan的完整有序actions；"
            "对象不明确时只填question。其余任务或混合查找后操作，business_plan=null，交完整业务规划，"
            "不能只执行已知的前半句。地点可引用当前真实id/名称或从1开始的序号，不编造对象。"
            "搜索时context仅填本次变更，未说日期/出发地不补、不要求填种类。"
            "origin、明确距离须逐字原话quote；日期单独temporal引用原话并解析，由程序运算。"
            "仅要求出发地或当前位置周边时填写nearby_quote；已指定城市不强求设备定位。"
            "清空须clear_fields及clear_quote，交通更正须travel_mode_quote。"
            "directions是可选检索办法，不是用户新条件。宽泛目的给3至5种不同办法，"
            "用具体可检索的单个活动词，不直接搜索抽象感受。明确活动/任选/同时满足/排除要忠实理解，"
            "不要把任选拼成一个复合关键词，不以偏好充当硬限制。"
            "地区由context限定，keyword不重复城市；不要固定景点分类。"
            "只有实际活动/时效/设施需要网页资料时才给一条research_query，否则null。",
            {"conversation": conversation, "current_context": context,
             "location_available": location_available, "previous_places": previous_cards,
             "view": {key: value for key, value in (view or {}).items() if key != "recent_conversation"},
             "intake_tools": [{"name": name, "description": TOOL_CATALOG[name].description,
                               "parameters": TOOL_CATALOG[name].parameters.model_json_schema()}
                              for name in sorted(INTAKE_TOOLS)],
             "recent_conversation": (view or {}).get("recent_conversation", []),
             "calendar": [{"date": (today + timedelta(days=i)).isoformat(),
                           "weekday": (today + timedelta(days=i)).isoweekday()} for i in range(14)]}, 1400)
        return RetrievalPlan(
            intent=value.intent, context=value.context, temporal=value.temporal,
            business_plan=value.business_plan if value.intent == "business" else None,
            goal=conversation[-1]["content"], nearby_quote=value.nearby_quote,
            clear_fields=value.clear_fields, clear_quote=value.clear_quote,
            travel_mode_quote=value.travel_mode_quote,
            directions=[RetrievalDirection(experience=d.experience, map_query=d.keyword,
                        web_query=value.research_query or d.keyword) for d in value.directions],
            web_queries=[value.research_query] if value.research_query else [],
        )

    def candidate_view(self, cards):
        return task_model_facts(cards)

    def choose(self, conversation, context, cards, published):
        facts, references = self.candidate_view(cards)
        value = structured_call(self.provider, "select_task_results", TaskSelection,
            "直接根据用户完整需求，从真实候选选至多6个最值得去的地点，每个写具体理由。"
            "原话是需求，检索词只是寻找办法；宽泛需求优先不同实际体验，明确活动不能被替换。"
            "保留明确排除和限制，不把未说的维度加入评估。天气仅在有日期时、路线仅有出发点时使用，"
            "地图评分只作同类弱参考。不输出匹配分、审查表或自创条件编号。"
            "拒绝多个地点总称、行政范围、场地占位；地图坐标不能使总称变成独立去处。"
            "候选必须是给定place.id，不能创造地点。只用本地点sources的引用id；"
            "忽略错绑/邻近/合集资料，不把别处特征借给此处。"
            "理由20至60字，只选能证明的具体事实及活动适配，不编安静、设备、开放保证或品牌关系。"
            "登记业态可支持常态业务，不能证明具体设施或活动排期。限时活动必须有实际资料证明时间适合。"
            "不用来源核验过程、资料不足提醒填充理由。已有活动标签沿用published的标签，"
            "同类内部择优，不用名称修辞伪造多样性。不得重复published里的地点。"
            "有符合需求的地点就选择；只有关键事实不足以选择时，research_query给一条具体补查词，否则null。",
            {"conversation": conversation, "context": context, "candidates": facts,
             "published": published}, 2200)
        for card in value.cards:
            card.evidence_ids = [references.get(ref, ref) for ref in card.evidence_ids]
        return value


class DiscoveryTaskWorkflow(DiscoveryWorkflow):
    selection_window = 12
    def __init__(self, *args, gate=None, research_shortlist=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.research_shortlist = research_shortlist
        self.gate = gate or ModelGate(2)
        self.budget = ExecutionBudget(self.cancelled, self.started + 90, model_limit=3, search_limit=1)
        self.trace = ExecutionTrace()

    def snapshot(self):
        value = super().snapshot()
        value["workflow"] = "task-v1"
        value["metrics"]["budget_used"] = self.budget.counts
        value["metrics"]["execution"] = self.trace.snapshot()
        value["metrics"]["research_shortlist"] = self.research_shortlist
        return value

    def check(self):
        try:
            self.budget.check()
        except ExecutionStopped as error:
            raise Stopped(str(error)) from error

    def model_call(self, stage, call):
        self.check()
        queued = time.monotonic()
        with self.gate.slot(self.budget):
            self.budget.reserve("model")
            self.metrics["model_calls"] += 1
            started = time.monotonic()
            with capture_model_usage() as receipt:
                try:
                    return self.measured(stage, call)  # No identical-prompt repair loop.
                finally:
                    self.trace.record(stage, started, time.monotonic(),
                        queue_ms=round(1000 * (started - queued)), usage=receipt.get("usage"))

    def search_area(self):
        return self.context.region

    def web_search(self, query):
        scoped = " ".join(filter(None, [self.search_area(), query]))
        def fetch():
            self.budget.reserve("search")
            self.metrics["web_attempts"] += 1
            return self.search.search(scoped)
        return self.cached("task-web-scoped-v2", scoped, 21600, fetch)

    def retrieve_tasks(self):
        tasks = [("map", query) for query in dict.fromkeys(d.map_query for d in self.plan.directions)]
        if self.plan.web_queries:
            tasks.append(("web", self.plan.web_queries[0]))
        values = self.parallel("retrieval", tasks, lambda task:
                               self.map_search(task[1]) if task[0] == "map" else self.web_search(task[1]))
        self.map_results = [(query, result or []) for (kind, query), result in zip(tasks, values, strict=True) if kind == "map"]
        self.research_sources = [source for (kind, _), result in zip(tasks, values, strict=True)
                                 if kind == "web" for source in (result or [])]
        candidates = select_retrieved_places(self.map_results, limit=18)
        if self.knowledge:
            known = self.knowledge.sources_for(candidates)
            self.research_sources.extend(source for sources in known.values() for source in sources)
            self.metrics["public_place_hits"] = sum(bool(sources) for sources in known.values())
        # Research the actual map shortlist, rather than asking the model to
        # turn registration metadata into detailed descriptions. One shared
        # search covers a few distinct retrieval leads; attribution still runs
        # per venue in ingest/passage_view. Never add a second upfront search.
        if self.research_shortlist and candidates and self.search is not None and not self.plan.web_queries:
            missing = [p for p in candidates[:3]
                       if not any(source_mentions_place(p, s) for s in self.research_sources)]
            if missing:
                names = list(dict.fromkeys(p["name"] for p in missing))
                query = " OR ".join('"' + name.replace('"', ' ') + '"' for name in names)
                try:
                    self.research_sources.extend(self.web_search(query))
                except ProviderError as error:
                    self.errors.append({"tool": "source_retrieval", "code": error.code})
        self.ingest(candidates)
        self.remember_public()
        return [place["id"] for place in candidates]

    def candidate_facts(self, ids):
        cards = []
        for key in ids:
            place, sources = self.places[key], []
            for evidence in self.evidence.values():
                if evidence["place_id"] != key:
                    continue
                if evidence["kind"] == "map_record":
                    sources.extend(map_fact_passages(place, evidence))
                elif evidence["kind"] in {"web_page", "search_excerpt"}:
                    sources.extend(passage_view(place, evidence, []))
            cards.append({"place": place, "sources": sources,
                          "route": self.routes.get(key), "weather": self.forecasts.get(key)})
        return copy.deepcopy(cards)

    def selection_supported(self, card, item):
        sources = {source['id']: source for source in card['sources']} if card else {}
        return bool(card and len(set(item.evidence_ids)) == len(item.evidence_ids)
                    and set(item.evidence_ids) <= sources.keys()
                    and any(sources[ref]['kind'] in {'map_record', 'web_page', 'search_excerpt'}
                            for ref in item.evidence_ids))

    def choose_and_publish(self, ids):
        cards = self.candidate_facts(self.facts(ids))
        if not cards:
            return None
        owner, execution, context = self.scope, self.execution_id, self.context.model_dump(mode="json")
        signature = hashlib.sha256(json.dumps(cards, sort_keys=True).encode()).digest()
        selected = self.model_call("selection", lambda: self.model.choose(
            self.turns, context, cards, [{"id": c["place"]["id"], "experience": c["experience"]} for c in self.cards]))
        self.check()
        with self.lock:
            if (owner != self.scope or execution != self.execution_id or context != self.context.model_dump(mode="json")
                    or signature != hashlib.sha256(json.dumps(self.candidate_facts([c["place"]["id"] for c in cards]), sort_keys=True).encode()).digest()):
                raise ValueError("任务或事实已变化，不能发布旧结果。")
            available = {c["place"]["id"]: c for c in cards}
            shown = {c["place"]["id"] for c in self.cards}
            pending, reserve = [], []
            primary_ids = {item.place_id for item in selected.cards}
            for item in selected.cards + getattr(selected, 'reserve_cards', []):
                card = available.get(item.place_id)
                if item.place_id in shown:
                    continue
                sources = {s["id"]: s for s in card["sources"]} if card else {}
                if not self.selection_supported(card, item):
                    self.errors.append({"tool": "selection", "code": "unbound_candidate_or_citation"})
                    continue
                cited = [sources[ref] for ref in item.evidence_ids]
                cited += [s for s in card["sources"] if s["kind"] == "map_record"]
                record_ids = list(dict.fromkeys(s["evidence_id"] for s in cited))
                facts = selection_facts([card], [item])[item.place_id]
                published_sources = []
                for ref in record_ids:
                    source = copy.deepcopy(self.evidence[ref])
                    selected_facts = [fact for fact in facts if fact["source_id"] == ref]
                    if selected_facts:
                        source["excerpt"] = "\n\n".join(
                            fact["label"] + "：" + fact["text"] for fact in selected_facts)
                    published_sources.append(source)
                (pending if item.place_id in primary_ids else reserve).append({"place": card["place"], "experience": item.experience, "reason": item.reason,
                                "sources": published_sources,
                                "route": card["route"], "weather": card["weather"]})
                shown.add(item.place_id)
            if hasattr(self, 'prepare_publication'):
                pending = self.prepare_publication(pending, reserve)
            self._append_cards(pending, [], reviewed=False)
        return selected

    def run(self):
        try:
            self.stage = "正在理解这次想法"
            previous_cards = [{"id": c["place"]["id"], "name": c["place"]["name"],
                               "experience": c["experience"]} for c in self.previous.get("cards", [])]
            key = [self.model.version, self.turns, self.context.model_dump(mode="json"),
                   self.location.model_dump() if self.location else None,
                   self.body.view.model_dump(), [m.model_dump() for m in self.body.conversation], previous_cards,
                   self.search_request]
            key.append(self.body.explore_mode)
            if self.body.location_details and (self.body.location_details.source == 'selected' or self.body.location_details.replace_origin):
                key.append(self.body.location_details.model_dump())
            self.plan = RetrievalPlan.model_validate(self.cached("task-plan-v1", key, 300,
                lambda: self.load_plan(self.context.model_dump(mode="json"), previous_cards)))
            if hasattr(self, 'explore_mode'):
                self.explore_mode = self.plan.explore_mode if self.previous.get('cards') else None
                self.update_exploration_context()
            if self.plan.intent == "business":
                self.status = "completed"
                return
            if getattr(self, 'use_exploration_reserve', lambda: False)():
                return
            self.configure_plan()
            if not self.center and (not self.context.region or self.context.max_distance_km is not None):
                self.request_location, self.status = True, "completed"
                return
            self.stage = "正在寻找不同的去处"
            ids = self.measured("retrieval", self.retrieve_tasks)
            self.stage = "正在整理合适的去处"
            chosen = self.choose_and_publish(ids[:self.selection_window])
            if not self.cards and chosen and chosen.research_query and not self.metrics["web_attempts"]:
                self.research_sources.extend(self.web_search(chosen.research_query))
                self.ingest(list(self.places.values()))
                self.choose_and_publish(ids[:self.selection_window])
            elif self.cards:
                shown = {c["place"]["id"] for c in self.cards}
                remaining = [key for key in ids if key not in shown]
                if remaining:
                    self.choose_and_publish(remaining[:self.selection_window])
            elif len(ids) > self.selection_window:
                # An empty first window is not an exhausted retrieval. In
                # particular, route filtering can remove it before any model
                # selection, leaving the later real candidates unexamined.
                self.choose_and_publish(ids[self.selection_window:])
            self.status = "completed" if self.cards and not self.errors else "partial" if self.cards else "failed"
        except (ProviderError, ValueError, KeyError, Stopped, ExecutionStopped) as error:
            logger.warning('discovery_task_failed stage=%s error_type=%s code=%s',
                self.stage, type(error).__name__, getattr(error, 'code', 'invalid_result'))
            self.errors.append({"tool": "task_workflow", "code": getattr(error, "code", type(error).__name__)})
            self.status = "cancelled" if self.cancelled.is_set() else "partial" if self.cards else "failed"
        finally:
            self.stage = ""
            if not (self.plan and self.plan.intent == "business"):
                self.reply = "已找到这些去处。" if self.cards else "" if self.request_location else "这轮查询尚未完成。"
