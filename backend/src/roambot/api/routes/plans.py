from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from roambot.api.dependencies import (
    RequestSession,
    get_provider_bundle,
    get_session_factory,
    get_settings,
    require_csrf,
    require_session,
)
from roambot.api.plan_models import OwnedEnvelope, PlanList, PublicEnvelope
from roambot.services.plans import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])
public_router = APIRouter(prefix="/public/plans", tags=["public plans"])
ANONYMOUS_COOKIE = "roambot_plan_identity"
OWNER = Depends(require_session)
WRITE = Depends(require_csrf)
FACTORY = Depends(get_session_factory)
BUNDLE = Depends(get_provider_bundle)
SETTINGS = Depends(get_settings)


def get_plan_service(factory=FACTORY):
    return PlanService(factory)


SERVICE = Depends(get_plan_service)
Name = Annotated[str, Field(min_length=1, max_length=100)]


class CreatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    history_id: str
    candidate_ids: list[str] = Field(min_length=2, max_length=3)
    name: Name | None = None
    expected_count: int | None = Field(default=None, ge=1, le=100)

    @field_validator("candidate_ids")
    @classmethod
    def unique(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("候选不能重复")
        return value


class UpdatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name | None = None
    expected_count: int | None = Field(default=None, ge=1, le=100)


class Vote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_id: str
    acceptable_ids: list[str] = Field(default_factory=list, max_length=3)


class Join(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nickname: str = Field(min_length=1, max_length=32)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str


@router.post("", status_code=201, response_model=OwnedEnvelope)
def create(body: CreatePlan, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.create(session.authenticated.user_id, body)}


@router.get("", response_model=PlanList)
def list_plans(session: RequestSession = OWNER, service=SERVICE):
    return {"plans": service.list(session.authenticated.user_id)}


@router.get("/{plan_id}", response_model=OwnedEnvelope)
def detail(plan_id: str, session: RequestSession = OWNER, service=SERVICE):
    return {"plan": service.detail(session.authenticated.user_id, plan_id)}


@router.patch("/{plan_id}", response_model=OwnedEnvelope)
def update(plan_id: str, body: UpdatePlan, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.update(session.authenticated.user_id, plan_id, body)}


@router.delete("/{plan_id}", status_code=204)
def delete(plan_id: str, session: RequestSession = WRITE, service=SERVICE):
    service.delete(session.authenticated.user_id, plan_id)
    return Response(status_code=204)


@router.delete("/{plan_id}/participants/{participant_id}", status_code=204)
def remove_participant(
    plan_id: str, participant_id: str, session: RequestSession = WRITE, service=SERVICE
):
    service.remove_participant(session.authenticated.user_id, plan_id, participant_id)
    return Response(status_code=204)


@router.post("/{plan_id}/invite/rotate")
def rotate_invite(
    plan_id: str, response: Response, session: RequestSession = WRITE, service=SERVICE
):
    response.headers["Cache-Control"] = "no-store"
    return service.rotate_invite(session.authenticated.user_id, plan_id)


@router.delete("/{plan_id}/invite", status_code=204)
def revoke_invite(plan_id: str, session: RequestSession = WRITE, service=SERVICE):
    service.revoke(session.authenticated.user_id, plan_id)
    return Response(status_code=204)


@router.put("/{plan_id}/vote", response_model=OwnedEnvelope)
def owner_vote(plan_id: str, body: Vote, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.owner_vote(session.authenticated.user_id, plan_id, body)}


@router.put("/{plan_id}/decision", response_model=OwnedEnvelope)
def decide(plan_id: str, body: Decision, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.decide(session.authenticated.user_id, plan_id, body.candidate_id)}


@router.put("/{plan_id}/voting-close", response_model=OwnedEnvelope)
def close_voting(plan_id: str, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.close_voting(session.authenticated.user_id, plan_id)}


@router.delete("/{plan_id}/decision", response_model=OwnedEnvelope)
def reopen(plan_id: str, session: RequestSession = WRITE, service=SERVICE):
    return {"plan": service.decide(session.authenticated.user_id, plan_id)}


@router.post("/{plan_id}/weather-checks", response_model=OwnedEnvelope)
def weather_check(plan_id: str, session: RequestSession = WRITE, service=SERVICE, bundle=BUNDLE):
    return {"plan": service.check_weather(session.authenticated.user_id, plan_id, bundle)}


@public_router.get("/{invite_token}", response_model=PublicEnvelope)
def public_detail(invite_token: str, request: Request, response: Response, service=SERVICE):
    identity = request.cookies.get(ANONYMOUS_COOKIE)
    data = service.public(invite_token, identity)
    csrf = service.refresh_anonymous_csrf(identity)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return {"plan": data, "anonymous_csrf": csrf}


@public_router.post("/{invite_token}/join", response_model=PublicEnvelope)
def join(
    invite_token: str,
    body: Join,
    request: Request,
    response: Response,
    service=SERVICE,
    settings=SETTINGS,
):
    data, identity, csrf = service.join(
        invite_token, request.cookies.get(ANONYMOUS_COOKIE), body.nickname
    )
    response.set_cookie(
        ANONYMOUS_COOKIE,
        identity,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        max_age=365 * 86400,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return {"plan": data, "anonymous_csrf": csrf}


@public_router.put("/{invite_token}/vote", response_model=PublicEnvelope)
def guest_vote(
    invite_token: str, body: Vote, request: Request, response: Response, service=SERVICE
):
    response.headers["Cache-Control"] = "no-store"
    return {
        "plan": service.guest_vote(
            invite_token,
            request.cookies.get(ANONYMOUS_COOKIE),
            request.headers.get("X-Plan-CSRF"),
            body,
        ),
        "anonymous_csrf": request.headers.get("X-Plan-CSRF"),
    }
