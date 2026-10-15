"""Execute only registered business tasks through the existing authorization boundary."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from roambot.domain.assistant import AssistantDraft, AssistantPatch, merge_assistant_patch
from roambot.domain.business_tools import TOOL_CATALOG, resolve_reference
from roambot.domain.models import (
    PlaceEvaluationRequest,
    PlaceEvaluationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from roambot.security.assistant_context import FactCandidate, FactDestination, FactSuitability


class BusinessFailure(ValueError):
    def __init__(self, code, message, *, uncertain=False, status=422):
        super().__init__(message)
        self.code, self.uncertain, self.status = code, uncertain, status


def segment(value):
    return quote(str(value), safe="")


def safe_result(value):
    if isinstance(value, dict):
        return {
            k: safe_result(v)
            for k, v in value.items()
            if k not in {"anonymous_csrf", "csrf_token", "session_token"}
        }
    if isinstance(value, list):
        return [safe_result(v) for v in value]
    return value


class BusinessExecutor:
    def __init__(self, request, context):
        self.request, self.context = request, context
        self.cookies = []
        headers = {
            key: request.headers[key]
            for key in ("x-csrf-token", "x-plan-csrf")
            if key in request.headers
        }
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=request.app, raise_app_exceptions=False),
            base_url="https://roambot.internal",
            headers=headers,
            cookies=dict(request.cookies),
        )

    async def close(self):
        await self.client.aclose()

    async def call(self, method, path, body=None, headers=None):
        # All callers construct paths from fixed task routes and encoded bound identifiers.
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise ValueError("工具不接受任意网络地址。")
        response = await self.client.request(method, "/api/v1" + path, json=body, headers=headers)
        self.cookies.extend(response.headers.get_list("set-cookie"))
        if response.status_code == 204:
            return {}
        try:
            data = response.json()
        except ValueError:
            raise BusinessFailure(
                "invalid_response", "服务器响应未完成，请核对实际状态。", uncertain=method != "GET"
            ) from None
        if not response.is_success:
            error = data.get("error", {})
            raise BusinessFailure(
                error.get("code", "request_failed"),
                error.get("message", "操作未完成。"),
                uncertain=response.status_code >= 500 and method != "GET",
                status=response.status_code,
            )
        return data

    async def history(self):
        history_id = self.context.get("history_id")
        if not history_id:
            raise ValueError("请先登录并使用当前推荐结果。")
        return (await self.call("GET", "/history/" + segment(history_id)))["history"]

    async def places(self):
        if self.context.get("page") == "/favorites":
            rows = await self.resource_list("favorites")
            return [{"id": r["id"], "name": r["name"]} for r in rows]
        if self.context.get("history_id"):
            result = (await self.history())["result"]
        elif self.context.get("latest_result"):
            result = self.context["latest_result"]
        else:
            turn = self.context.get("assistant_turn") or {}
            token = turn.get("assistant_context")
            if not token:
                return []
            facts = self.request.app.state.assistant_context_signer.verify(token)
            return [{"id": c.candidate_id, "name": c.destination.name} for c in facts.candidates]
        items = result.get("items") or ([result["item"]] if result.get("item") else [])
        return [
            {"id": i["destination"]["provider_id"], "name": i["destination"]["name"], "item": i}
            for i in items
        ]

    async def plan(self):
        if self.context.get("invite_token"):
            token = segment(self.context["invite_token"])
            data = await self.call("GET", "/public/plans/" + token)
        elif self.context.get("plan_id"):
            data = await self.call("GET", "/plans/" + segment(self.context["plan_id"]))
        else:
            raise ValueError("请先明确要操作的计划。")
        expected = self.context.get("resource_version")
        if expected and expected != data["plan"]["updated_at"]:
            raise ValueError("计划已变化，请刷新后重新发起操作。")
        return data["plan"]

    async def ui_places(self):
        # Client presentation objects can drive local UI only, never backend writes.
        return self.context.get("visible_places") or await self.places()

    async def public_context(self):
        """Only compact, authorized descriptions go to the model, never cookies/tokens."""
        out = {
            "page": self.context.get("page"),
            "selected": self.context.get("selected_ids", []),
            "focused": self.context.get("focused_id"),
            "dirty": self.context.get("dirty", False),
            "layer": self.context.get("layer"),
            "today": str(datetime.now(timezone(timedelta(hours=8))).date()),
            "weather_date": self.context.get("weather_date"),
            "all_dates": self.context.get("all_dates", False),
        }
        try:
            out["places"] = [{"id": p["id"], "name": p["name"]} for p in await self.ui_places()]
        except BusinessFailure as exc:
            if exc.status not in {401, 404}:
                raise
            out["places"], out["stale_result"] = [], True
        if self.context.get("plan_id") or self.context.get("invite_token"):
            try:
                plan = await self.plan()
            except (ValueError, BusinessFailure):
                plan = None
            if plan is not None:
                out["plan"] = self.describe_plan(plan)
        page = self.context.get("page", "")
        current_kind = {"/favorites": "favorites", "/history": "history", "/plans": "plans"}.get(
            page
        )
        for kind in ("favorites", "history", "plans"):
            try:
                out[kind] = (await self.resource_list(kind))[:100]
            except BusinessFailure as exc:
                if exc.status not in {401, 404}:
                    raise
                out[kind], out["authentication_required"] = [], exc.status == 401
            except ValueError:
                out[kind] = []
                if kind == current_kind:
                    out["stale_list"] = True
        turn = self.context.get("assistant_turn") or {}
        out["draft"] = turn.get("draft", {})
        out["conversation"] = (self.context.get("conversation") or turn.get("history", []))[-6:]
        return out

    def describe_plan(self, plan):
        return {
            "id": plan["id"],
            "name": plan["name"],
            "status": plan["status"],
            "start_date": plan["start_date"],
            "end_date": plan["end_date"],
            "candidates": self.plan_candidates(plan),
            "participants": [
                {"id": p["id"], "name": p["nickname"]} for p in (plan.get("participants") or [])
            ],
            "my_vote": {
                k: (plan.get("me") or {}).get(k) for k in ("preferred_id", "acceptable_ids")
            },
        }

    def plan_candidates(self, plan):
        candidates = [
            {"id": c["id"], "name": c["snapshot"]["destination"]["name"]}
            for c in plan["candidates"]
        ]
        order = [p["id"] for p in self.context.get("visible_places", [])]
        if order and len(order) == len(candidates) and set(order) == {c["id"] for c in candidates}:
            return sorted(candidates, key=lambda item: order.index(item["id"]))
        return candidates

    async def resource_list(self, kind):
        data = await self.call("GET", "/" + kind)
        rows = data[{"history": "histories", "plans": "plans", "favorites": "favorites"}[kind]]
        objects = [
            {
                "id": r["id"],
                "name": r.get("name")
                or r.get("place", {}).get("name")
                or (r.get("city", "") + " " + r.get("start_date", "")),
            }
            for r in rows
        ]
        visible = self.context.get("visible_resources") or {}
        if visible.get("kind") == kind:
            order = visible["ids"]
            by_id = {item["id"]: item for item in objects}
            if len(set(order)) != len(order) or any(value not in by_id for value in order):
                raise ValueError("列表已变化，请刷新后重新指定对象。")
            return [by_id[value] for value in order]
        return objects

    async def resource(self, kind, target):
        focused = self.context.get(
            {"history": "history_id", "plans": "plan_id", "favorites": "focused_id"}[kind]
        )
        return resolve_reference(target, await self.resource_list(kind), focused=focused)

    def query_body(self):
        turn = self.context.get("assistant_turn") or {}
        draft = turn.get("draft", {})
        if not draft.get("main_origin") or not draft.get("start_date") or not draft.get("end_date"):
            raise ValueError("请先补充出发地和出行日期。")
        regions = draft.get("destination_regions") or []
        if not regions and not draft.get("max_distance_km"):
            raise ValueError("请先设置距离或目的地范围。")
        base = {
            key: draft[key]
            for key in ("main_origin", "companion_origins", "start_date", "end_date", "weights")
            if draft.get(key) is not None
        }
        base.update(city="", max_distance_km=500 if regions else draft["max_distance_km"])
        if draft.get("mode") == "place_evaluation":
            base["target_place"] = draft.get("target_place")
            return "/place-evaluations", PlaceEvaluationRequest.model_validate(base).model_dump(
                mode="json", exclude={"origin_count"}
            )
        if not any(
            draft.get(k)
            for k in ("scenery_types", "destination_regions", "scenery_query", "scenery_keywords")
        ):
            raise ValueError("请先说明想找的地方或目的地范围。")
        base.update(
            scenery_types=draft.get("scenery_types")
            or ["lake", "sea", "old_town", "museum", "park", "mountain"],
            destination_regions=regions,
        )
        for key in ("scenery_query", "scenery_keywords", "scenery_match_mode"):
            if draft.get(key) is not None:
                base[key] = draft[key]
        return "/recommendations", RecommendationRequest.model_validate(base).model_dump(
            mode="json", exclude={"origin_count"}
        )

    async def execute(self, action, message):
        spec = TOOL_CATALOG[action.tool]
        args = action.validated_arguments().model_dump(exclude_none=True)
        name = action.tool
        if name == "describe_capabilities":
            return {
                "reply": "可以直接修改条件并查询、查看详情和地图、选择或比较地点、管理收藏和历史，"
                "以及创建和管理计划、邀请、本人投票、天气复查与定案。可随时说返回、刷新、"
                "向下看、打开更多功能；Alt+/ 回到当前对话。登录密码在安全表单中输入。"
            }
        if spec.kind == "ui":
            effect = {"tool": name, "arguments": args}
            if name in {"open_detail", "open_map", "open_external_map"}:
                place = resolve_reference(
                    args.get("place"),
                    await self.ui_places(),
                    focused=self.context.get("focused_id"),
                )
                effect["arguments"] = {"id": place["id"]}
                self.context["focused_id"] = place["id"]
            elif name == "select_candidates":
                places = await self.ui_places()
                ids = [resolve_reference(ref, places)["id"] for ref in args["places"]]
                if len(set(ids)) != len(ids):
                    raise ValueError("所选候选不能重复。")
                self.context["selected_ids"] = ids
                effect["arguments"] = {"ids": ids}
            elif name == "show_comparison" and len(self.context.get("selected_ids", [])) < 2:
                raise ValueError("请选择至少两个候选再比较。")
            elif name == "show_day_explanation":
                plan = await self.plan()
                candidates = self.plan_candidates(plan)
                candidate = resolve_reference(args.get("place"), candidates)
                effect["arguments"] = {"id": candidate["id"]}
            return {"effect": effect}
        if name in {"update_search_conditions", "explain_result"}:
            turn = self.context.get("assistant_turn")
            if turn and self.context.get("conversation"):
                turn["history"] = self.context["conversation"][-6:]
            page = self.context.get("page", "")
            if name == "explain_result" and page != "/recommend":
                result = None
                token = None
                if self.context.get("plan_id") or self.context.get("invite_token"):
                    plan = await self.plan()
                    facts = []
                    for candidate in plan["candidates"]:
                        item = dict(candidate["snapshot"])
                        check = candidate.get("latest_weather")
                        if check:
                            item["weather"] = check.get("weather") or []
                            item["daily_suitability"] = check.get("daily_suitability") or []
                        destination = item["destination"]
                        facts.append(
                            FactCandidate(
                                candidate_id=candidate["id"],
                                destination=FactDestination(
                                    name=destination["name"],
                                    city=destination["city"],
                                    type_name="",
                                    scenery_tags=sorted(destination["scenery_tags"]),
                                    rating=destination.get("rating"),
                                ),
                                # Plans intentionally omit personal origin routes.
                                distances=[],
                                weather=item["weather"],
                                daily_suitability=[
                                    FactSuitability(
                                        date=d["date"], score=d["score"], status=d["status"]
                                    )
                                    for d in item["daily_suitability"]
                                ],
                                group_accessibility=item["group_accessibility"],
                                score=item["score"],
                            )
                        )
                    token = self.request.app.state.assistant_context_signer.issue_facts(
                        facts, plan["candidates"][0]["snapshot"]["source_state"]["kind"]
                    )
                elif page.startswith("/history/") and self.context.get("history_id"):
                    raw = (await self.history())["result"]
                    model = RecommendationResponse if "items" in raw else PlaceEvaluationResponse
                    result = model.model_validate(raw)
                if result is not None:
                    token = self.request.app.state.assistant_context_signer.issue(result)
                if token is not None:
                    turn = {
                        "message": message,
                        "revision": 0,
                        "draft": {},
                        "history": self.context.get("conversation", []),
                        "assistant_context": token,
                    }
            if not turn:
                return {"effect": {"tool": "continue_in_studio", "arguments": {"message": message}}}
            response = await self.call("POST", "/assistant/turns", {**turn, "message": message})
            if response.get("patch"):
                today = datetime.now(timezone(timedelta(hours=8))).date()
                merged = merge_assistant_patch(
                    AssistantDraft.model_validate(turn["draft"]),
                    AssistantPatch.model_validate(response["patch"]),
                    today,
                    validate_existing_dates=False,
                )
                turn["draft"] = merged.model_dump(mode="json", exclude_none=True)
                turn["conversation_state"] = response.get("conversation_state", {})
                self.context["dirty"] = True
            return {"assistant": response}
        if name == "run_recommendation":
            if not self.context.get("assistant_turn"):
                return {"effect": {"tool": "continue_in_studio", "arguments": {"message": message}}}
            path, body = self.query_body()
            result = await self.call("POST", path, body)
            self.context.update(
                latest_result=result,
                history_id=result.get("history_id"),
                selected_ids=[],
                dirty=False,
            )
            return {"query": result, "query_request": body}
        if name.startswith("list_"):
            kind = {
                "list_favorites": "favorites",
                "list_history": "history",
                "list_plans": "plans",
            }[name]
            return {
                "data": await self.call("GET", "/" + kind),
                "effect": {"tool": "navigate", "arguments": {"page": kind}},
            }
        if name == "favorite_place":
            place = resolve_reference(
                args.get("place"), await self.places(), focused=self.context.get("focused_id")
            )
            if not place.get("item"):
                raise ValueError("请先登录并更新推荐，再收藏此地点。")
            source = (await self.history())["result"]["source_state"]["kind"]
            provider = "mock" if source == "demo" else "amap"
            return await self.call(
                "POST",
                "/favorites",
                {"provider": provider, "destination": place["item"]["destination"]},
            )
        if name == "remove_favorite":
            favorite = await self.resource("favorites", args.get("target"))
            return await self.call("DELETE", "/favorites/" + segment(favorite["id"]))
        if name == "evaluate_favorite":
            favorite = await self.resource("favorites", args.get("target"))
            return {
                "effect": {"tool": "evaluate_favorite", "arguments": {"name": favorite["name"]}}
            }
        if name in {
            "open_history",
            "rerun_history",
            "delete_history",
            "create_share",
            "revoke_share",
            "clear_history",
        }:
            return await self.history_action(name, args)
        if name == "create_plan_from_selection":
            if self.context.get("dirty"):
                raise ValueError("条件已修改，请先更新推荐。")
            places = await self.places()
            references = args.pop("places", None)
            ids = (
                [resolve_reference(p, places)["id"] for p in references]
                if references
                else self.context.get("selected_ids", [])
            )
            if not 2 <= len(ids) <= 3 or len(set(ids)) != len(ids):
                raise ValueError("请选择2–3个不同候选。")
            allowed = {p["id"] for p in places}
            if any(value not in allowed for value in ids):
                raise ValueError("候选不属于当前推荐。")
            args.pop("places", None)
            body = {"history_id": self.context.get("history_id"), "candidate_ids": ids, **args}
            result = await self.call("POST", "/plans", body)
            self.context["plan_id"] = result["plan"]["id"]
            return {
                **result,
                "effect": {"tool": "open_plan", "arguments": {"id": result["plan"]["id"]}},
            }
        if name == "join_plan":
            token = self.context.get("invite_token")
            if not token:
                raise ValueError("请先打开有效的邀请链接。")
            return safe_result(
                await self.call("POST", "/public/plans/" + segment(token) + "/join", args)
            )
        if name == "logout":
            return {**await self.call("POST", "/auth/logout"), "auth_changed": True}
        return await self.plan_action(name, args)

    async def history_action(self, name, args):
        if name == "clear_history":
            return await self.call("DELETE", "/history")
        if name == "revoke_share":
            share_id = self.context.get("share_id")
            if not share_id:
                from sqlalchemy import select

                from roambot.api.dependencies import get_session_factory
                from roambot.persistence.tables import ShareTable

                history = await self.resource("history", args.get("target"))
                with get_session_factory(self.request)() as db:
                    share_id = db.scalar(
                        select(ShareTable.id).where(
                            ShareTable.history_id == history["id"], ShareTable.revoked_at.is_(None)
                        )
                    )
            if not share_id:
                raise ValueError("当前历史没有有效分享。")
            return await self.call("DELETE", "/shares/" + segment(share_id))
        history = await self.resource("history", args.get("target"))
        history_id = history["id"]
        self.context["history_id"] = history_id
        path = "/history/" + segment(history_id)
        if name == "delete_history":
            return await self.call("DELETE", path)
        if name == "create_share":
            result = await self.call("POST", path + "/share")
            self.context["share_id"] = result["share"]["id"]
            return result
        result = await self.call(
            "POST" if name == "rerun_history" else "GET",
            path + ("/rerun" if name == "rerun_history" else ""),
        )
        return {**result, "effect": {"tool": "open_history", "arguments": {"id": history_id}}}

    async def plan_action(self, name, args):
        reference = args.pop("plan", None)
        if reference is not None:
            target = await self.resource("plans", reference)
            if target["id"] != self.context.get("plan_id"):
                self.context.pop("resource_version", None)
                self.context.pop("invite_token", None)
                self.context["visible_places"] = []
            self.context["plan_id"] = target["id"]
        if name in {"open_plan", "update_plan", "delete_plan"}:
            plan = await self.resource("plans", args.pop("target", None))
            self.context["plan_id"] = plan["id"]
        plan = await self.plan()
        path = "/plans/" + segment(plan["id"])
        if name == "open_plan":
            return {"plan": plan, "effect": {"tool": "open_plan", "arguments": {"id": plan["id"]}}}
        if name == "update_plan":
            if not args:
                raise ValueError("请说明要修改的名称或人数。")
            return await self.call("PATCH", path, args)
        if name == "delete_plan":
            return await self.call("DELETE", path)
        if name == "remove_participant":
            people = [{"id": p["id"], "name": p["nickname"]} for p in plan["participants"]]
            person = resolve_reference(args.get("target"), people)
            return await self.call("DELETE", path + "/participants/" + segment(person["id"]))
        if name in {"submit_vote", "decide_plan"}:
            candidates = self.plan_candidates(plan)
            if name == "decide_plan":
                body = {"candidate_id": resolve_reference(args.get("place"), candidates)["id"]}
                return await self.call("PUT", path + "/decision", body)
            previous = plan.get("me") or {}
            if not args:
                raise ValueError("请说明首选或可接受的地点。")
            preferred = (
                resolve_reference(args["preferred"], candidates)["id"]
                if "preferred" in args
                else previous.get("preferred_id")
            )
            if not preferred:
                raise ValueError("请先选择一个首选地点。")
            body = {
                "preferred_id": preferred,
                "acceptable_ids": (
                    [resolve_reference(r, candidates)["id"] for r in args["acceptable"]]
                    if "acceptable" in args
                    else previous.get("acceptable_ids") or []
                ),
            }
            if self.context.get("invite_token"):
                public_path = "/public/plans/" + segment(self.context["invite_token"])
                public = await self.call("GET", public_path)
                return safe_result(
                    await self.call(
                        "PUT",
                        public_path + "/vote",
                        body,
                        headers={"X-Plan-CSRF": public.get("anonymous_csrf") or ""},
                    )
                )
            return await self.call("PUT", path + "/vote", body)
        routes = {
            "rotate_invite": ("POST", "/invite/rotate"),
            "revoke_invite": ("DELETE", "/invite"),
            "close_voting": ("PUT", "/voting-close"),
            "reopen_voting": ("DELETE", "/decision"),
            "check_plan_weather": ("POST", "/weather-checks"),
        }
        if name not in routes:
            raise ValueError("工具尚未接入执行器。")
        method, suffix = routes[name]
        return await self.call(method, path + suffix)
