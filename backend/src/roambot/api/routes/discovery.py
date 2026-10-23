"""Versioned prototype, independent of the old mandatory six-type query."""

import threading
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Request, Response

from roambot.api.dependencies import (
    AuthApiError,
    get_optional_session,
    get_provider_bundle,
    require_optional_csrf,
    require_csrf,
    get_personal_data_service,
)
from roambot.api.errors import error_response
from roambot.api.routes.commands import actor_for
from roambot.domain.discovery import DiscoveryRequest
from roambot.persistence.discovery_cache import DiscoveryCache
from roambot.persistence.discovery_knowledge import DiscoveryKnowledge
from roambot.providers.amap import AMapProvider
from roambot.providers.discovery import (
    DiscoveryMap,
    TavilySearch,
    review_batch,
)
from roambot.providers.discovery_workflow import DiscoveryModel
from roambot.services.discovery import DiscoveryJobs, DiscoveryRun
from roambot.services.personal_data import ResourceNotFoundError
from roambot.services.discovery_workflow import DiscoveryWorkflow
from roambot.services.discovery_orchestrator import DiscoveryOrchestrator
from roambot.services.discovery_execution import ModelGate

router = APIRouter(prefix="/discovery", tags=["open discovery"])
_lock = threading.Lock()
BUNDLE = Depends(get_provider_bundle)
CSRF = Depends(require_optional_csrf)
SESSION = Depends(get_optional_session)


def get_jobs(request: Request):
    with _lock:
        if not hasattr(request.app.state, "discovery_jobs"):
            request.app.state.discovery_jobs = DiscoveryJobs()
        return request.app.state.discovery_jobs


def get_discovery_factory(request: Request, bundle=BUNDLE):
    raw = request.app.state.provider_runtime._adapters
    if not isinstance(raw.places, AMapProvider):
        raise AuthApiError(
            status_code=503,
            code="configuration_error",
            message="新推荐原型需要真实模型与地图配置。",
        )
    key = request.app.state.settings.discovery_search_api_key
    if key is None or not key.get_secret_value().strip():
        raise AuthApiError(
            status_code=503,
            code="discovery_search_not_configured",
            message="新推荐的资料服务尚未配置。",
        )
    with _lock:
        if not hasattr(request.app.state, "discovery_model_gate"):
            request.app.state.discovery_model_gate = ModelGate(2)
        if not hasattr(request.app.state, "discovery_cache"):
            request.app.state.discovery_cache = DiscoveryCache(
                request.app.state.settings.data_dir / "discovery-facts.sqlite3"
            )
            request.app.state.discovery_knowledge = DiscoveryKnowledge(
                request.app.state.settings.data_dir / "discovery-public.sqlite3"
            )
    cache = request.app.state.discovery_cache

    def factory(body, previous):
        search = TavilySearch(key.get_secret_value())
        if getattr(request.app.state, "discovery_orchestration_mode", "legacy") == "source":
            from roambot.services.discovery_sources import DiscoverySourceModel, DiscoverySourceWorkflow

            return DiscoverySourceWorkflow(
                body, DiscoveryMap(raw.places), bundle.weather, search,
                DiscoverySourceModel(bundle.assistant), cache, "", previous,
                map_interval=0.55, knowledge=request.app.state.discovery_knowledge,
                gate=request.app.state.discovery_model_gate,
            )
        if getattr(request.app.state, "discovery_orchestration_mode", "legacy") == "task":
            from roambot.services.discovery_tasks import DiscoveryTaskModel, DiscoveryTaskWorkflow

            return DiscoveryTaskWorkflow(
                body, DiscoveryMap(raw.places), bundle.weather, search,
                DiscoveryTaskModel(bundle.assistant), cache, "", previous,
                map_interval=0.55, knowledge=request.app.state.discovery_knowledge,
                gate=request.app.state.discovery_model_gate,
            )
        coordinated = getattr(request.app.state, "discovery_orchestration_mode", "legacy") == "coordinated"
        extra = {"gate": request.app.state.discovery_model_gate,
                 "batch_reviewer": lambda conversation, context, cards: review_batch(
                     bundle.assistant, conversation, context, cards)} if coordinated else {}
        implementation = DiscoveryOrchestrator if coordinated else DiscoveryWorkflow
        run = implementation(
            body,
            DiscoveryMap(raw.places),
            bundle.weather,
            search,
            DiscoveryModel(bundle.assistant),
            cache,
            "",
            previous,
            reviewer=lambda cards: review_batch(
                bundle.assistant, run.turns, run.review_context(), cards
            ),
            map_interval=0.55,
            knowledge=request.app.state.discovery_knowledge,
            **extra,
        )
        return run

    return factory


JOBS = Depends(get_jobs)
FACTORY = Depends(get_discovery_factory)
PERSONAL = Depends(get_personal_data_service)
OWNER_WRITE = Depends(require_csrf)


@router.post("/jobs")
def start(
    body: DiscoveryRequest,
    request: Request,
    response: Response,
    session=CSRF,
    jobs=JOBS,
    factory=FACTORY,
    personal=PERSONAL,
):
    response.headers["Cache-Control"] = "no-store"
    actor = actor_for(request, response, session)
    try:
        capture = (lambda run: personal.capture_discovery(user_id=session.authenticated.user_id,
            body=body, snapshot={**run.snapshot(), "status": run.status}).id) if session else None
        key = jobs.start(actor, body, factory, on_complete=capture)
        return {"id": key}
    except LookupError:
        return error_response(
            status_code=404, code="discovery_not_found", message="原推荐会话不可用。"
        )
    except ValueError as error:
        return error_response(status_code=429, code="discovery_busy", message=str(error))


@router.post("/jobs/{job_id}/history")
def save_history(job_id: str, request: Request, response: Response, session=OWNER_WRITE,
    jobs=JOBS, personal=PERSONAL):
    try:
        run = jobs.owned(actor_for(request, response, session), job_id)
        with run.lock:
            if run.status not in {"completed", "partial"} or not run.cards:
                return error_response(status_code=409, code="discovery_not_ready", message="推荐尚未完成。")
            if run.history_id is None:
                run.history_id = personal.capture_discovery(user_id=session.authenticated.user_id,
                    body=run.body, snapshot={**run.snapshot(), "status": run.status}).id
            personal.get_history(user_id=session.authenticated.user_id, history_id=run.history_id)
        return {"history_id": run.history_id}
    except (LookupError, ResourceNotFoundError):
        return error_response(status_code=404, code="discovery_not_found", message="推荐会话不可用。")


def history_run(personal, user_id, history_id):
    history = personal.get_history(user_id=user_id, history_id=history_id)
    if history.mode != "discovery":
        raise LookupError()
    body = DiscoveryRequest(message=history.request["message"], location=history.request.get("location"))
    run = DiscoveryRun(body, None, None, None, None, previous={
        "context": history.request["context"], "cards": history.result["cards"],
        "search_request": history.request.get('search_request')},
        source=history.result["source"])
    run.cards = history.result["cards"]
    # Preserve the actual bounded dialogue that produced this snapshot. The
    # latest message may be only a correction, not the original leisure goal.
    if history.request.get("conversation"):
        run.turns = history.request["conversation"]
    run.status = history.result["status"]
    run.stage = ""
    run.history_id = history.id
    return run


@router.post("/history/{history_id}/restore")
def restore_history(history_id: str, request: Request, response: Response, session=OWNER_WRITE,
    jobs=JOBS, personal=PERSONAL):
    response.headers["Cache-Control"] = "no-store"
    try:
        run = history_run(personal, session.authenticated.user_id, history_id)
        key = jobs.restore(actor_for(request, response, session), run)
        return {"id": key, **jobs.owned(actor_for(request, response, session), key).snapshot()}
    except (LookupError, ResourceNotFoundError):
        return error_response(status_code=404, code="history_not_found", message="历史快照不可用。")
    except ValueError as error:
        return error_response(status_code=429, code="discovery_busy", message=str(error))


class RerunDiscovery(BaseModel):
    message: str | None = Field(default=None, min_length=1, max_length=2000)


@router.post("/history/{history_id}/rerun")
def rerun_history(history_id: str, request: Request, response: Response, body: RerunDiscovery | None = None,
    session=OWNER_WRITE, jobs=JOBS, personal=PERSONAL, factory=FACTORY):
    try:
        previous = history_run(personal, session.authenticated.user_id, history_id)
        if (not body or not body.message) and previous.context.start_date and previous.context.start_date < datetime.now(timezone(timedelta(hours=8))).date():
            return error_response(status_code=422, code="history_dates_expired", message="这次改到哪天？")
        actor = actor_for(request, response, session)
        source = jobs.restore(actor, previous)
        message = body.message if body and body.message else previous.body.message
        next_body = DiscoveryRequest(message=message, previous_id=source, location=previous.body.location)
        capture = lambda run: personal.capture_discovery(user_id=session.authenticated.user_id,
            body=next_body, snapshot={**run.snapshot(), "status": run.status}).id
        key = jobs.start(actor, next_body, factory, on_complete=capture)
        return {"id": key, "message": message}
    except (LookupError, ResourceNotFoundError):
        return error_response(status_code=404, code="history_not_found", message="历史快照不可用。")
    except ValueError as error:
        return error_response(status_code=429, code="discovery_busy", message=str(error))


@router.get("/jobs/{job_id}")
def read(job_id: str, request: Request, response: Response, session=SESSION, jobs=JOBS):
    response.headers["Cache-Control"] = "no-store"
    try:
        run = jobs.owned(actor_for(request, response, session), job_id)
        return {"id": job_id, **run.snapshot()}
    except LookupError:
        return error_response(
            status_code=404, code="discovery_not_found", message="推荐会话不可用。"
        )


@router.delete("/jobs/{job_id}")
def stop(job_id: str, request: Request, response: Response, session=CSRF, jobs=JOBS):
    try:
        jobs.stop(actor_for(request, response, session), job_id)
        return {"cancelled": True}
    except LookupError:
        return error_response(
            status_code=404, code="discovery_not_found", message="推荐会话不可用。"
        )
