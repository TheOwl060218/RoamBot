"""Optional chat and direct buttons share these ownership-checked operations."""
import copy
from fastapi import APIRouter, Depends, Query, Request, Response

from roambot.api.dependencies import (get_session_factory, get_optional_session,
    require_optional_csrf, get_personal_data_service, get_provider_bundle)
from roambot.api.routes.commands import actor_for
from roambot.domain.itineraries import CreateItinerary, EditItinerary, AddStop, TransferStop, SaveOrder, GenerateRoute
from roambot.providers.amap import AMapProvider
from roambot.providers.discovery import DiscoveryMap
from roambot.services.itineraries import ItineraryService, fail
from roambot.services.itinerary_routing import ItineraryRouter

router = APIRouter(prefix='/itineraries', tags=['itineraries'])
SESSION, WRITE = Depends(get_optional_session), Depends(require_optional_csrf)
FACTORY, PERSONAL = Depends(get_session_factory), Depends(get_personal_data_service)


def get_itinerary_service(factory=FACTORY):
    return ItineraryService(factory)


SERVICE = Depends(get_itinerary_service)


def owner_for(request, response, session):
    response.headers['Cache-Control'] = 'no-store'
    return 'user:' + session.authenticated.user_id if session else actor_for(request, response, None)


def get_itinerary_router(request: Request, bundle=Depends(get_provider_bundle)):
    adapter = request.app.state.provider_runtime._adapters.places
    if not isinstance(adapter, AMapProvider):
        fail('routing_unavailable', '实际路线服务尚未配置，地点和安排仍可保存。', 503)
    return ItineraryRouter(DiscoveryMap(adapter), bundle.weather, map_interval=.55)


@router.get('')
def list_itineraries(request: Request, response: Response, session=SESSION, service=SERVICE):
    return service.list(owner_for(request, response, session))


@router.post('', status_code=201)
def create(body: CreateItinerary, request: Request, response: Response, session=WRITE, service=SERVICE):
    return {'itinerary': service.create(owner_for(request, response, session), body.name)}


@router.get('/{key}')
def read(key: str, request: Request, response: Response, session=SESSION, service=SERVICE):
    return {'itinerary': service.get(owner_for(request, response, session), key)}


@router.patch('/{key}')
def edit(key: str, body: EditItinerary, request: Request, response: Response, session=WRITE, service=SERVICE):
    return {'itinerary': service.edit(owner_for(request, response, session), key, body)}


def bound_card(body, request, response, session, personal):
    if body.source_job_id:
        jobs = getattr(request.app.state, 'discovery_jobs', None)
        try:
            snapshot = jobs.owned(actor_for(request, response, session), body.source_job_id).snapshot() if jobs else None
        except LookupError:
            snapshot = None
        if not snapshot: fail('source_not_found', '推荐会话已失效，请从历史恢复后再加入。', 404)
    elif body.history_id:
        if not session: fail('authentication_required', '请先登录后使用历史。', 401)
        from roambot.services.personal_data import ResourceNotFoundError
        try: history = personal.get_history(user_id=session.authenticated.user_id, history_id=body.history_id)
        except ResourceNotFoundError: fail('source_not_found', '历史不可用。', 404)
        if history.mode != 'discovery': fail('source_not_supported', '请使用推荐地点或收藏加入行程。')
        snapshot = history.result
    else:
        if not session: fail('authentication_required', '请先登录后使用收藏。', 401)
        favorite = next((v for v in personal.list_favorites(session.authenticated.user_id) if v.id == body.favorite_id), None)
        if favorite is None: fail('source_not_found', '收藏不存在。', 404)
        p = favorite.place
        return {'place': {'id': p.provider+':'+p.provider_place_id, 'name': p.name,
            'city': p.city, 'address': p.address, 'map_type': p.type_name, 'map_url': '', 'facts': {},
            'coordinate': {'longitude': p.longitude, 'latitude': p.latitude, 'system': 'gcj02'}}, 'experience': ''}
    card = next((c for c in snapshot['cards'] if c['place']['id'] == body.place_id), None)
    if card is None: fail('place_not_found', '地点不属于当前推荐。', 404)
    return copy.deepcopy(card)


@router.post('/{key}/stops')
def add(key: str, body: AddStop, request: Request, response: Response, session=WRITE, service=SERVICE, personal=PERSONAL):
    owner = owner_for(request, response, session)
    service.get(owner, key)  # Authorize target before touching any source.
    return service.add(owner, key, bound_card(body, request, response, session, personal))


@router.post('/{key}/stops/{stop_id}/move')
def transfer(key: str, stop_id: str, body: TransferStop, request: Request, response: Response, session=WRITE, service=SERVICE):
    return service.transfer(owner_for(request, response, session), key, stop_id, body)


@router.delete('/{key}/stops/{stop_id}')
def remove(key: str, stop_id: str, request: Request, response: Response,
           version: int = Query(ge=1), session=WRITE, service=SERVICE):
    return {'itinerary': service.remove(owner_for(request, response, session), key, stop_id, version)}


@router.put('/{key}/order')
def order(key: str, body: SaveOrder, request: Request, response: Response, session=WRITE, service=SERVICE):
    return {'itinerary': service.order(owner_for(request, response, session), key, body)}


@router.post('/{key}/generate')
def generate(key: str, body: GenerateRoute, request: Request, response: Response, session=WRITE,
             service=SERVICE, routing=Depends(get_itinerary_router)):
    owner = owner_for(request, response, session)
    doc, repeated = service.claim_generation(owner, key, body)
    if repeated: return {'itinerary': service.get(owner, key)}
    try:
        result = routing.generate(doc, body.optimize, body.request_id)
        result.pop('generating_since', None)
        return {'itinerary': service.commit_generation(owner, key, doc['version'], result)}
    except Exception:
        # Release only this unchanged claim. A concurrent edit must survive.
        doc.pop('generating_since', None)
        try: service.commit_generation(owner, key, doc['version'], doc)
        except Exception: pass
        raise
