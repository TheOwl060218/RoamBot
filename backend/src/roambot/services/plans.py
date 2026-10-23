"""Trusted snapshots and transactional plan operations."""

import json
import unicodedata
from datetime import UTC, date, datetime, time, timedelta, timezone
from hmac import digest
from secrets import compare_digest
from uuid import uuid4

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError

from roambot.domain.models import Coordinate, DailyWeather, SceneryType
from roambot.domain.scoring import score_daily_weather
from roambot.domain.discovery_snapshot import DiscoveryArchive, DiscoveryArchiveRequest, DiscoveryPlanSnapshot
from roambot.persistence.tables import (
    HistoryTable,
    PlanAcceptableTable,
    PlanAnonymousSessionTable,
    PlanCandidateTable,
    PlanInviteTable,
    PlanParticipantTable,
    PlanVoteTable,
    PlanWeatherCheckTable,
    TravelPlanTable,
    UserTable,
)
from roambot.providers.protocols import ProviderError
from roambot.security.sessions import hash_token, new_token
from roambot.services.personal_data import _origin_labels, _remove_private_strings, public_discovery_snapshot
from roambot.services.snapshot_metadata import display_city

CHINA = timezone(timedelta(hours=8))


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat()


class PlanError(Exception):
    def __init__(self, code, message, status=422):
        self.code, self.message, self.status = code, message, status


def normalized(value):
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def anonymous_csrf(identity):
    # The random HttpOnly identity is the secret; opening another tab must not rotate it.
    return digest(identity.encode("utf-8"), b"roambot-plan-csrf-v1", "sha256").hex()


def plan_name(city, start, end, year):
    def display(value):
        return (
            value[5:].replace("-", ".") if int(value[:4]) == year else value[2:].replace("-", ".")
        )

    first, last = display(start), display(end)
    return f"{city} {first}{'–' + last if end != start else ''} 出行计划"


def weather_risk(weather, tags):
    scores = [
        score_daily_weather(
            DailyWeather.model_validate(day), frozenset(SceneryType(t) for t in tags)
        ).score
        for day in weather
    ]
    worst = min(scores)
    return "high" if worst < 50 else "caution" if worst < 75 else "stable"


def risk_change(before, after):
    order = {"stable": 0, "caution": 1, "high": 2}
    delta = order[after] - order[before]
    if delta < 0:
        return "improved"
    if delta > 0:
        return "worsened" if after == "high" else "attention"
    return "stable"


class PlanService:
    def __init__(self, factory, clock=None):
        self.factory = factory
        self.clock = clock or (lambda: datetime.now(UTC))

    def owned(self, db, user_id, plan_id):
        plan = db.scalar(
            select(TravelPlanTable).where(
                TravelPlanTable.id == plan_id, TravelPlanTable.owner_user_id == user_id
            )
        )
        if plan is None:
            raise PlanError("plan_not_found", "计划不存在。", 404)
        return plan

    def candidates(self, db, plan):
        return list(
            db.scalars(
                select(PlanCandidateTable)
                .where(PlanCandidateTable.plan_id == plan.id)
                .order_by(PlanCandidateTable.position)
            )
        )

    def create(self, user_id, body):
        now = self.clock()
        with self.factory.begin() as db:
            history = db.scalar(
                select(HistoryTable).where(
                    HistoryTable.id == body.history_id, HistoryTable.user_id == user_id
                )
            )
            if history is None:
                raise PlanError("plan_not_found", "历史不存在或不属于当前账户。", 404)
            if history.mode == "discovery":
                return self.create_discovery(db, user_id, body, history, now)
            if history.mode != "recommendation":
                raise PlanError("history_not_eligible", "请使用登录后产生的推荐结果。")
            request, result = json.loads(history.request_json), json.loads(history.result_json)
            available = {i["destination"]["provider_id"]: i for i in result["items"]}
            if any(cid not in available for cid in body.candidate_ids):
                raise PlanError("candidate_not_in_history", "所选候选不在本次历史中。")
            city = display_city(request, [available[cid] for cid in body.candidate_ids])
            plan = TravelPlanTable(
                id=str(uuid4()),
                owner_user_id=user_id,
                name=body.name
                or plan_name(
                    city,
                    request["start_date"],
                    request["end_date"],
                    now.astimezone(CHINA).year,
                ),
                city=city,
                start_date=request["start_date"],
                end_date=request["end_date"],
                expected_count=body.expected_count or 1 + len(request["companion_origins"]),
                status="voting",
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            db.flush()
            private = tuple(
                sorted(
                    {
                        request["main_origin"],
                        *request["companion_origins"],
                        *_origin_labels(result["items"]),
                    },
                    key=len,
                    reverse=True,
                )
            )
            for position, cid in enumerate(body.candidate_ids):
                item = available[cid]
                destination = item["destination"]
                snapshot = {
                    key: item[key]
                    for key in (
                        "weather",
                        "daily_suitability",
                        "score",
                        "explanation",
                        "overall_advice",
                        "group_accessibility",
                    )
                }
                snapshot["destination"] = {
                    key: destination.get(key)
                    for key in ("name", "address", "city", "scenery_tags", "rating")
                }
                snapshot["source_state"] = result["source_state"]
                snapshot = _remove_private_strings(snapshot, private)
                db.add(
                    PlanCandidateTable(
                        id=str(uuid4()),
                        plan_id=plan.id,
                        provider_id=cid,
                        position=position,
                        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                        longitude=destination["coordinate"]["longitude"],
                        latitude=destination["coordinate"]["latitude"],
                    )
                )
            user = db.get(UserTable, user_id)
            db.add(
                PlanParticipantTable(
                    id=str(uuid4()),
                    plan_id=plan.id,
                    user_id=user_id,
                    nickname=user.username,
                    normalized_nickname=normalized(user.username),
                    role="owner",
                    joined_at=now,
                )
            )
            db.flush()
            return self.serialize(db, plan)

    def create_discovery(self, db, user_id, body, history, now):
        query = DiscoveryArchiveRequest.model_validate_json(history.request_json)
        result = DiscoveryArchive.model_validate_json(history.result_json)
        start = body.start_date or query.context.start_date
        end = body.end_date or query.context.end_date
        if not start or not end:
            raise PlanError("plan_dates_required", "计划安排哪天？")
        today = now.astimezone(CHINA).date()
        if start < today or end < start or end > today + timedelta(days=6):
            raise PlanError("plan_dates_invalid", "计划日期请选在未来七天内。")
        available = {c.place.id: c for c in result.cards}
        if any(cid not in available for cid in body.candidate_ids):
            raise PlanError("candidate_not_in_history", "所选候选不在本次历史中。")
        public = public_discovery_snapshot(query.model_dump(mode="json"), result.model_dump(mode="json"), user_id)
        public_cards = {c.place.id: p for c, p in zip(result.cards, public['cards'], strict=True)}
        city = "、".join(dict.fromkeys(available[cid].place.city for cid in body.candidate_ids))
        plan = TravelPlanTable(id=str(uuid4()), owner_user_id=user_id,
            name=body.name or plan_name(city, start.isoformat(), end.isoformat(), today.year),
            city=city, start_date=start.isoformat(), end_date=end.isoformat(),
            expected_count=body.expected_count or 1, status="voting", created_at=now, updated_at=now)
        db.add(plan); db.flush()
        for position, cid in enumerate(body.candidate_ids):
            card = available[cid]
            public_card = public_cards[cid]
            weather = public_card['weather'] or []
            weather = [day for day in weather if start.isoformat() <= day['date'] <= end.isoformat()]
            snapshot = DiscoveryPlanSnapshot(destination=public_card['place'], experience=public_card['experience'],
                reason=public_card['reason'], sources=public_card['sources'], weather=weather, source=result.source)
            db.add(PlanCandidateTable(id=str(uuid4()), plan_id=plan.id, provider_id=cid, position=position,
                snapshot_json=snapshot.model_dump_json(), longitude=card.place.coordinate.longitude,
                latitude=card.place.coordinate.latitude))
        user = db.get(UserTable, user_id)
        db.add(PlanParticipantTable(id=str(uuid4()), plan_id=plan.id, user_id=user_id,
            nickname=user.username, normalized_nickname=normalized(user.username), role="owner", joined_at=now))
        db.flush()
        return self.serialize(db, plan)

    def list(self, user_id):
        with self.factory() as db:
            plans = db.scalars(
                select(TravelPlanTable)
                .where(TravelPlanTable.owner_user_id == user_id)
                .order_by(TravelPlanTable.created_at.desc())
            )
            return [self.serialize(db, plan) for plan in plans]

    def detail(self, user_id, plan_id):
        with self.factory() as db:
            return self.serialize(db, self.owned(db, user_id, plan_id))

    def update(self, user_id, plan_id, body):
        with self.factory.begin() as db:
            plan = self.owned(db, user_id, plan_id)
            for key, value in body.model_dump(exclude_none=True).items():
                setattr(plan, key, value)
            plan.updated_at = self.clock()
            return self.serialize(db, plan)

    def delete(self, user_id, plan_id):
        with self.factory.begin() as db:
            db.delete(self.owned(db, user_id, plan_id))

    def remove_participant(self, user_id, plan_id, participant_id):
        with self.factory.begin() as db:
            self.owned(db, user_id, plan_id)
            participant = db.scalar(
                select(PlanParticipantTable).where(
                    PlanParticipantTable.id == participant_id,
                    PlanParticipantTable.plan_id == plan_id,
                    PlanParticipantTable.role == "guest",
                )
            )
            if participant is None:
                raise PlanError("plan_not_found", "参与者不存在。", 404)
            db.delete(participant)

    def rotate_invite(self, user_id, plan_id):
        now = self.clock()
        with self.factory.begin() as db:
            plan = self.owned(db, user_id, plan_id)
            self.revoke_in_db(db, plan_id, now)
            token = new_token()
            expires = datetime.combine(
                date.fromisoformat(plan.end_date) + timedelta(days=8), time.min, CHINA
            ).astimezone(UTC)
            if expires <= now:
                raise PlanError("invite_expired", "已超过邀请有效期。")
            db.add(
                PlanInviteTable(
                    id=str(uuid4()),
                    plan_id=plan_id,
                    token_hash=hash_token(token),
                    created_at=now,
                    expires_at=expires,
                )
            )
            return {"url": f"/join/{token}", "expires_at": expires}

    def revoke_in_db(self, db, plan_id, now):
        db.execute(
            update(PlanInviteTable)
            .where(PlanInviteTable.plan_id == plan_id, PlanInviteTable.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def revoke(self, user_id, plan_id):
        with self.factory.begin() as db:
            self.owned(db, user_id, plan_id)
            self.revoke_in_db(db, plan_id, self.clock())

    def invited(self, db, token):
        invite = db.scalar(
            select(PlanInviteTable).where(PlanInviteTable.token_hash == hash_token(token))
        )
        if invite is None:
            raise PlanError("plan_not_found", "邀请不可用。", 404)
        if invite.revoked_at is not None:
            raise PlanError("invite_revoked", "邀请已撤销，请向发起者索取新链接。", 404)
        if invite.expires_at.replace(tzinfo=UTC) <= self.clock():
            raise PlanError("invite_expired", "邀请已过期。", 404)
        return db.get(TravelPlanTable, invite.plan_id)

    def anonymous(self, db, plan_id, identity):
        if not identity:
            return None
        return db.scalar(
            select(PlanParticipantTable).where(
                PlanParticipantTable.plan_id == plan_id,
                PlanParticipantTable.anonymous_hash == hash_token(identity),
            )
        )

    def public(self, token, identity):
        with self.factory() as db:
            plan = self.invited(db, token)
            return self.serialize(db, plan, self.anonymous(db, plan.id, identity), public=True)

    def join(self, token, identity, nickname):
        now = self.clock()
        identity = identity or new_token()
        try:
            with self.factory.begin() as db:
                db.execute(text("BEGIN IMMEDIATE"))
                plan = self.invited(db, token)
                self.require_active(plan)
                if plan.status != "voting":
                    raise PlanError("vote_closed", "投票已结束，不能加入。", 409)
                participant = self.anonymous(db, plan.id, identity)
                if participant is None:
                    participant = PlanParticipantTable(
                        id=str(uuid4()),
                        plan_id=plan.id,
                        nickname=nickname,
                        normalized_nickname=normalized(nickname),
                        anonymous_hash=hash_token(identity),
                        role="guest",
                        joined_at=now,
                    )
                    db.add(participant)
                csrf = anonymous_csrf(identity)
                anonymous_session = db.get(PlanAnonymousSessionTable, hash_token(identity))
                if anonymous_session is None:
                    db.add(
                        PlanAnonymousSessionTable(
                            token_hash=hash_token(identity),
                            csrf_hash=hash_token(csrf),
                            created_at=now,
                        )
                    )
                else:
                    anonymous_session.csrf_hash = hash_token(csrf)
                db.flush()
                return self.serialize(db, plan, participant, public=True), identity, csrf
        except IntegrityError as exc:
            raise PlanError("nickname_taken", "该昵称已有人使用，请换一个。", 409) from exc

    def refresh_anonymous_csrf(self, identity):
        if not identity:
            return None
        with self.factory.begin() as db:
            row = db.get(PlanAnonymousSessionTable, hash_token(identity))
            if row is None:
                return None
            csrf = anonymous_csrf(identity)
            if not compare_digest(row.csrf_hash, hash_token(csrf)):
                row.csrf_hash = hash_token(csrf)
            return csrf

    def save_vote(self, db, plan, participant, body):
        self.require_active(plan)
        if plan.status != "voting":
            raise PlanError("vote_closed", "投票已结束，不能投票或改票。", 409)
        if participant is None:
            raise PlanError("participant_required", "请先加入计划。", 403)
        candidates = {c.provider_id: c.id for c in self.candidates(db, plan)}
        acceptable = set(body.acceptable_ids) | {body.preferred_id}
        if not acceptable <= candidates.keys():
            raise PlanError("candidate_not_in_history", "候选不属于此计划。")
        vote = db.get(PlanVoteTable, participant.id)
        if vote is None:
            vote = PlanVoteTable(
                participant_id=participant.id,
                preferred_candidate_id=candidates[body.preferred_id],
                updated_at=self.clock(),
            )
            db.add(vote)
        else:
            vote.preferred_candidate_id = candidates[body.preferred_id]
            vote.updated_at = self.clock()
            db.execute(
                delete(PlanAcceptableTable).where(
                    PlanAcceptableTable.participant_id == participant.id
                )
            )
        db.flush()
        for cid in acceptable:
            db.add(PlanAcceptableTable(participant_id=participant.id, candidate_id=candidates[cid]))
        plan.updated_at = self.clock()
        db.flush()

    def owner_vote(self, user_id, plan_id, body):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            plan = self.owned(db, user_id, plan_id)
            participant = db.scalar(
                select(PlanParticipantTable).where(
                    PlanParticipantTable.plan_id == plan_id, PlanParticipantTable.user_id == user_id
                )
            )
            self.save_vote(db, plan, participant, body)
            return self.serialize(db, plan)

    def guest_vote(self, token, identity, csrf, body):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            plan = self.invited(db, token)
            anonymous_session = db.get(PlanAnonymousSessionTable, hash_token(identity or ""))
            if (
                not csrf
                or anonymous_session is None
                or not compare_digest(anonymous_session.csrf_hash, hash_token(csrf))
            ):
                raise PlanError("anonymous_csrf_invalid", "请刷新页面后再投票。", 403)
            participant = self.anonymous(db, plan.id, identity)
            self.save_vote(db, plan, participant, body)
            return self.serialize(db, plan, participant, public=True)

    def require_active(self, plan):
        if plan.end_date < self.clock().astimezone(CHINA).date().isoformat():
            raise PlanError("plan_ended", "出行日期已结束，不能再修改投票或决定。", 409)

    def close_voting(self, user_id, plan_id):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            plan = self.owned(db, user_id, plan_id)
            self.require_active(plan)
            if plan.status == "decided":
                raise PlanError("invalid_plan_transition", "目的地已决定。", 409)
            if plan.status != "closed":
                plan.status = "closed"
                plan.updated_at = self.clock()
                db.flush()
            return self.serialize(db, plan)

    def decide(self, user_id, plan_id, candidate_id=None):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            plan = self.owned(db, user_id, plan_id)
            self.require_active(plan)
            if candidate_id is None:
                if plan.status not in {"closed", "decided"}:
                    raise PlanError("invalid_plan_transition", "投票已经开放。", 409)
                plan.status, plan.final_candidate_id, plan.decided_at = "voting", None, None
            else:
                if plan.status not in {"voting", "closed"}:
                    raise PlanError("invalid_plan_transition", "请先重新开放投票。", 409)
                if candidate_id not in {c.provider_id for c in self.candidates(db, plan)}:
                    raise PlanError("candidate_not_in_history", "候选不属于此计划。")
                plan.status, plan.final_candidate_id = "decided", candidate_id
                plan.decided_at = self.clock()
            plan.updated_at = self.clock()
            db.flush()
            return self.serialize(db, plan)

    def weather_checks(self, db, plan):
        return list(
            db.scalars(
                select(PlanWeatherCheckTable)
                .where(PlanWeatherCheckTable.plan_id == plan.id)
                .order_by(PlanWeatherCheckTable.checked_at.desc(), PlanWeatherCheckTable.id.desc())
            )
        )

    def check_weather(self, user_id, plan_id, bundle):
        now = self.clock()
        # Read a detached snapshot. Provider/cache I/O must not run under a SQLite write lock.
        with self.factory() as db:
            plan = self.owned(db, user_id, plan_id)
            previous = self.weather_checks(db, plan)
            self.require_weather_check(plan, previous, now)
            candidates = [
                c for c in self.candidates(db, plan)
                if plan.status != "decided" or c.provider_id == plan.final_candidate_id
            ]
            original_dates = (plan.start_date, plan.end_date)
            start = max(date.fromisoformat(plan.start_date), now.astimezone(CHINA).date())
            end = date.fromisoformat(plan.end_date)

        rows = []
        for candidate in candidates:
            snapshot = json.loads(candidate.snapshot_json)
            discovery = snapshot.get("schema_version") == "discovery-v1"
            tags = snapshot["destination"].get("scenery_tags", [])
            successful = next(
                (c for c in previous if c.candidate_id == candidate.id and c.status == "success"),
                None,
            )
            baseline = json.loads(successful.weather_json) if successful else snapshot["weather"]
            baseline = [
                day for day in baseline if start.isoformat() <= day["date"] <= end.isoformat()
            ]
            before = weather_risk(baseline, tags) if baseline and not discovery else None
            row = PlanWeatherCheckTable(
                id=str(uuid4()), plan_id=plan_id, candidate_id=candidate.id,
                triggered_by=user_id, checked_at=now, status="failed", source="unavailable",
                weather_json=None, risk=None, change="unavailable",
            )
            try:
                days = bundle.weather.daily(
                    Coordinate(longitude=candidate.longitude, latitude=candidate.latitude),
                    start,
                    end,
                )
                expected_dates = {start + timedelta(days=i) for i in range((end - start).days + 1)}
                if {day.date for day in days} != expected_dates:
                    raise ProviderError("unavailable", "Weather data incomplete")
                weather = [day.model_dump(mode="json") for day in days]
                risk = weather_risk(weather, tags) if not discovery else None
                row.status, row.source = "success", bundle.trace.to_source_state(3).kind.value
                row.weather_json, row.risk = json.dumps(weather, ensure_ascii=False), risk
                row.change = risk_change(before, risk) if before and risk else "stable"
            except ProviderError:
                pass
            rows.append(row)

        with self.factory.begin() as db:
            # Revalidate atomically after I/O: only one concurrent check may commit.
            db.execute(text("BEGIN IMMEDIATE"))
            plan = self.owned(db, user_id, plan_id)
            now = self.clock()
            self.require_weather_check(plan, self.weather_checks(db, plan), now)
            current_ids = {
                c.id for c in self.candidates(db, plan)
                if plan.status != "decided" or c.provider_id == plan.final_candidate_id
            }
            if (
                (plan.start_date, plan.end_date) != original_dates
                or not current_ids <= {r.candidate_id for r in rows}
            ):
                raise PlanError("invalid_plan_transition", "计划已更改，请重新检查天气。", 409)
            for row in rows:
                if row.candidate_id not in current_ids:
                    continue
                row.checked_at = now
                db.add(row)
            plan.updated_at = now
            db.flush()
            return self.serialize(db, plan)

    def require_weather_check(self, plan, previous, now):
        if plan.end_date < now.astimezone(CHINA).date().isoformat():
            raise PlanError("invalid_plan_transition", "出行已结束，不能再检查天气。", 409)
        if previous and previous[0].checked_at.replace(tzinfo=UTC) + timedelta(hours=1) > now:
            raise PlanError("weather_check_cooldown", "一小时内无需重复检查。", 429)

    def serialize(self, db, plan, participant=None, public=False):
        participants = db.scalars(
            select(PlanParticipantTable)
            .where(PlanParticipantTable.plan_id == plan.id)
            .order_by(PlanParticipantTable.joined_at)
        ).all()
        candidates = self.candidates(db, plan)
        candidate_map = {c.id: c.provider_id for c in candidates}
        participant_ids = [p.id for p in participants]
        votes = list(
            db.scalars(
                select(PlanVoteTable).where(PlanVoteTable.participant_id.in_(participant_ids))
            )
        )
        accepted = list(
            db.scalars(
                select(PlanAcceptableTable).where(
                    PlanAcceptableTable.participant_id.in_(participant_ids)
                )
            )
        )
        own_vote = next(
            (v for v in votes if participant and v.participant_id == participant.id), None
        )
        visible = not public or plan.status in {"closed", "decided"} or own_vote is not None
        summary = {
            "voted_count": len(votes),
            "joined_count": len(participants),
            "complete": len(votes) >= plan.expected_count,
            "candidates": [
                {
                    "id": c.provider_id,
                    "preferred_count": sum(v.preferred_candidate_id == c.id for v in votes),
                    "acceptable_count": sum(a.candidate_id == c.id for a in accepted),
                    "all_accept": bool(votes)
                    and sum(a.candidate_id == c.id for a in accepted) == len(votes),
                }
                for c in candidates
            ],
        }
        invites = db.scalar(
            select(PlanInviteTable).where(
                PlanInviteTable.plan_id == plan.id, PlanInviteTable.revoked_at.is_(None)
            )
        )
        data = {
            "id": plan.id,
            "name": plan.name,
            "city": plan.city,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "expected_count": plan.expected_count,
            "status": plan.status,
            "final_candidate_id": plan.final_candidate_id,
            "decided_at": iso(plan.decided_at),
            "created_at": iso(plan.created_at),
            "updated_at": iso(plan.updated_at),
            "ended": plan.end_date < self.clock().astimezone(CHINA).date().isoformat(),
            "participants": [
                {
                    "id": p.id,
                    "nickname": p.nickname,
                    "role": p.role,
                    "voted": any(v.participant_id == p.id for v in votes),
                }
                for p in participants
            ]
            if visible
            else None,
            "candidates": [
                {"id": c.provider_id, "snapshot": json.loads(c.snapshot_json)} for c in candidates
            ],
            "summary": summary if visible else None,
            "me": {
                "id": participant.id,
                "nickname": participant.nickname,
                "preferred_id": candidate_map[own_vote.preferred_candidate_id]
                if own_vote
                else None,
                "acceptable_ids": [
                    candidate_map[a.candidate_id]
                    for a in accepted
                    if a.participant_id == participant.id
                ],
            }
            if participant
            else None,
        }
        checks = self.weather_checks(db, plan)
        for candidate, serialized in zip(candidates, data["candidates"], strict=True):
            relevant = [c for c in checks if c.candidate_id == candidate.id]
            latest = relevant[0] if relevant else None
            successful = next((c for c in relevant if c.status == "success"), None)
            weather = json.loads(successful.weather_json) if successful else None
            tags = frozenset(
                SceneryType(tag) for tag in serialized["snapshot"]["destination"].get("scenery_tags", [])
            )
            serialized["latest_weather"] = (
                {
                    "checked_at": iso(latest.checked_at),
                    "status": latest.status,
                    "source": latest.source,
                    "change": latest.change,
                    "risk": successful.risk if successful else None,
                    "weather": weather,
                    "daily_suitability": [
                        score_daily_weather(DailyWeather.model_validate(day), tags).model_dump(
                            mode="json"
                        )
                        for day in (weather or []) if serialized["snapshot"].get("schema_version") != "discovery-v1"
                    ],
                    "last_success_at": iso(successful.checked_at) if successful else None,
                }
                if latest
                else None
            )
        data["next_weather_check_at"] = (
            checks[0].checked_at.replace(tzinfo=UTC) + timedelta(hours=1) if checks else None
        )
        if not public:
            owner = next((p for p in participants if p.role == "owner"), None)
            vote = next((v for v in votes if owner and v.participant_id == owner.id), None)
            data["me"] = (
                {
                    "id": owner.id,
                    "nickname": owner.nickname,
                    "preferred_id": candidate_map[vote.preferred_candidate_id] if vote else None,
                    "acceptable_ids": [
                        candidate_map[a.candidate_id]
                        for a in accepted
                        if a.participant_id == owner.id
                    ],
                }
                if owner
                else None
            )
            data["invite_active"] = bool(
                invites and invites.expires_at.replace(tzinfo=UTC) > self.clock()
            )
        return data
