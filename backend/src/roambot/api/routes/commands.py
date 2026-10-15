"""Propose then execute: client state can be checked before mutations start."""

import hashlib
import json
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool

from roambot.api.dependencies import (
    get_provider_bundle,
    get_session_factory,
    get_settings,
    require_optional_csrf,
)
from roambot.api.errors import error_response
from roambot.domain.business_tools import (
    TOOL_CATALOG,
    Action,
    BusinessPlan,
    CommandRequest,
    ExecutionRequest,
)
from roambot.persistence.command_log import CommandJournal, request_digest
from roambot.providers.assistant import MockAssistantProvider
from roambot.providers.business_planner import mock_business_plan
from roambot.providers.protocols import ProviderError
from roambot.services.assistant_limits import AssistantLimitError
from roambot.services.business_executor import BusinessExecutor, BusinessFailure, safe_result

router = APIRouter(prefix="/assistant/commands", tags=["assistant commands"])
CSRF = Depends(require_optional_csrf)
FACTORY = Depends(get_session_factory)
BUNDLE = Depends(get_provider_bundle)
COOKIE = "roambot_assistant_identity"


def get_business_planner(bundle=BUNDLE):
    provider = bundle.assistant
    if isinstance(provider, MockAssistantProvider):
        return mock_business_plan
    planner = getattr(provider, "plan_business", None)
    if planner is None:

        def unavailable(_request, _context):
            raise ProviderError("configuration_error", "操作助手尚未配置。")

        return unavailable
    return planner


PLANNER = Depends(get_business_planner)


def actor_for(request, response, session):
    if session is not None:
        scope = hashlib.sha256(session.session_token.encode()).hexdigest()[:32]
        return "user:" + session.authenticated.user_id + ":" + scope
    identity = request.cookies.get(COOKIE)
    if not identity:
        identity = str(uuid4())
        response.set_cookie(
            COOKIE,
            identity,
            httponly=True,
            samesite="lax",
            secure=get_settings(request).secure_cookies,
            max_age=86400,
        )
    return "guest:" + hashlib.sha256(identity.encode()).hexdigest()


def proposal_body(row):
    data = json.loads(row.data_json)
    actions = data.get("actions", [])
    return {
        "request_id": row.request_id,
        "proposal": row.proposal,
        "question": data.get("question"),
        "actions": actions,
        "requires_confirmation": any(TOOL_CATALOG[a["tool"]].destructive for a in actions),
    }


@router.get("/catalog")
def catalog():
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters.model_json_schema(),
                "kind": t.kind,
                "destructive": t.destructive,
            }
            for t in TOOL_CATALOG.values()
        ]
    }


@router.post("/proposals")
async def propose(
    body: CommandRequest,
    request: Request,
    response: Response,
    session=CSRF,
    factory=FACTORY,
    planner=PLANNER,
):
    response.headers["Cache-Control"] = "no-store"
    actor = actor_for(request, response, session)
    journal = CommandJournal(factory)
    raw = body.model_dump(mode="json")
    if not journal.reserve(actor, raw):
        row = journal.get(actor, body.request_id)
        if row.digest != request_digest(raw):
            return error_response(
                status_code=409, code="command_id_conflict", message="此操作编号已用于另一条请求。"
            )
        if row.status in {"planning", "rejected"}:
            return error_response(
                status_code=409,
                code="command_planning_incomplete",
                message="操作方案尚未完成，请重新发起。",
            )
        return proposal_body(row)
    executor = BusinessExecutor(request, raw["context"])
    try:
        context = await executor.public_context()
        key = request.client.host if request.client else "unknown"
        with request.app.state.assistant_limiter.acquire(key):
            selected = await run_in_threadpool(planner, body, context)
        plan = BusinessPlan.model_validate(selected)
        if plan.question and plan.actions:
            raise ValueError("需要澄清时不能同时执行。")
        if not plan.actions and not plan.question:
            raise ValueError("操作方案为空。")
        for action in plan.actions:
            action.validated_arguments()
            public = {
                "update_search_conditions",
                "explain_result",
                "run_recommendation",
                "join_plan",
                "describe_capabilities",
            }
            guest_vote = action.tool == "submit_vote" and body.context.invite_token
            if (
                session is None
                and TOOL_CATALOG[action.tool].kind == "backend"
                and action.tool not in public
                and not guest_vote
            ):
                raise BusinessFailure(
                    "authentication_required", "请先登录后执行此操作。", status=401
                )
            if action.tool in {"favorite_place", "create_plan_from_selection"}:
                await executor.history()
        data = {
            "command": raw,
            "working_context": raw["context"],
            "actions": [a.model_dump() for a in plan.actions],
            "question": plan.question,
            "steps": [],
        }
        journal.save(actor, body.request_id, "planned", data)
        return proposal_body(journal.get(actor, body.request_id))
    except (ProviderError, AssistantLimitError, ValueError) as exc:
        journal.save(actor, body.request_id, "rejected", {"command": raw})
        status = (
            exc.status
            if isinstance(exc, BusinessFailure)
            else (
                503
                if isinstance(exc, ProviderError)
                else 429
                if isinstance(exc, AssistantLimitError)
                else 422
            )
        )
        return error_response(
            status_code=status, code=getattr(exc, "code", "invalid_command"), message=str(exc)
        )
    finally:
        await executor.close()


@router.post("/execute")
async def execute(
    body: ExecutionRequest, request: Request, response: Response, session=CSRF, factory=FACTORY
):
    response.headers["Cache-Control"] = "no-store"
    actor = actor_for(request, response, session)
    journal = CommandJournal(factory)
    try:
        row = journal.get(actor, body.request_id, body.proposal)
    except LookupError:
        return error_response(
            status_code=404, code="command_not_found", message="操作不存在或不属于当前会话。"
        )
    data = json.loads(row.data_json)
    if row.status == "completed":
        return data["response"]
    if journal.expired(row):
        return error_response(
            status_code=409, code="command_expired", message="操作已过期，请重新发起。"
        )
    if proposal_body(row)["requires_confirmation"] and not body.confirmed:
        return error_response(
            status_code=409, code="command_confirmation_required", message="请确认这些操作后执行。"
        )
    if not journal.claim(actor, body.request_id):
        return error_response(
            status_code=409,
            code="command_busy_or_uncertain",
            message="操作正在执行或结果待核对，请先查看实际业务状态。",
        )
    executor = BusinessExecutor(request, data["working_context"])
    steps = [s for s in data["steps"] if s["status"] == "completed"]
    data["steps"] = steps
    status, failure = "completed", {}
    try:
        for index in range(len(steps), len(data["actions"])):
            action = Action.model_validate(data["actions"][index])
            # Record the boundary before invoking a mutation. A process crash cannot replay it.
            data["in_flight"] = index
            journal.save(actor, body.request_id, "running", data)
            try:
                result = safe_result(await executor.execute(action, data["command"]["message"]))
            except (ValueError, httpx.HTTPError) as exc:
                uncertain = getattr(exc, "uncertain", False) or not isinstance(exc, ValueError)
                status = "uncertain" if uncertain else "failed"
                failure = {
                    "failed_step": index,
                    "error": {"code": getattr(exc, "code", "invalid_object"), "message": str(exc)},
                }
                break
            steps.append({"tool": action.tool, "status": "completed", "result": result})
            if result.get("plan", {}).get("updated_at"):
                data["working_context"]["resource_version"] = result["plan"]["updated_at"]
            data.pop("in_flight", None)
            journal.save(actor, body.request_id, "running", data)
            question = result.get("assistant", {}).get("question")
            if question:
                status = "awaiting_input"
                data["question"] = question
                break
        result = {"status": status, "steps": steps, "question": data.get("question"), **failure}
        data["response"] = result
        journal.save(actor, body.request_id, status, data)
        for cookie in executor.cookies:
            response.headers.append("set-cookie", cookie)
        return result
    finally:
        await executor.close()
