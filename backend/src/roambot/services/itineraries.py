"""Private itinerary documents; never share the recommendation's mutable identity."""

import copy
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text, update

from roambot.persistence.tables import ItineraryTable, ItineraryWorkspaceTable
from roambot.services.plans import PlanError


def fail(code, message, status=422):
    raise PlanError(code, message, status=status)


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def dates(start, end):
    if not start or not end:
        return []
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def changed(doc):
    doc["route_status"] = "dirty" if doc["days"] else "none"
    doc["updated_at"] = datetime.now(UTC).isoformat()
    doc.pop("last_generation_request", None)
    return doc


class ItineraryService:
    def __init__(self, factory):
        self.factory = factory

    @staticmethod
    def owned(db, owner, key):
        row = db.get(ItineraryTable, key)
        if row is None or row.owner != owner:
            fail("itinerary_not_found", "行程不存在或不属于当前账户。", 404)
        return row

    @staticmethod
    def document(row, private=False):
        doc = json.loads(row.document_json) | {"id": row.id, "version": row.revision}
        if not private:
            doc.pop("route_cache", None)
        return doc

    @staticmethod
    def write(db, row, doc, expected=None):
        if expected is not None and row.revision != expected:
            fail("itinerary_changed", "行程已在其他页面修改，请刷新后继续。", 409)
        revision = row.revision
        result = db.execute(
            update(ItineraryTable)
            .where(ItineraryTable.id == row.id, ItineraryTable.revision == revision)
            .values(document_json=dump(doc), revision=revision + 1)
        )
        if result.rowcount != 1:
            fail("itinerary_changed", "行程已变化，请刷新后继续。", 409)

    def list(self, owner):
        with self.factory() as db:
            rows = db.scalars(
                select(ItineraryTable)
                .where(ItineraryTable.owner == owner)
                .order_by(ItineraryTable.created_at.desc(), ItineraryTable.id)
            ).all()
            workspace = db.get(ItineraryWorkspaceTable, owner)
            return {
                "itineraries": [self.document(r) for r in rows],
                "current_id": workspace.current_id if workspace else (rows[0].id if rows else None),
            }

    def get(self, owner, key, private=False):
        with self.factory() as db:
            return self.document(self.owned(db, owner, key), private)

    def create(self, owner, name):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            rows = db.scalars(select(ItineraryTable.id).where(ItineraryTable.owner == owner)).all()
            if len(rows) >= 50:
                fail("itinerary_limit", "目前最多保存50个行程。")
            now, key = datetime.now(UTC), str(uuid4())
            doc = {
                "name": name,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "start_date": None,
                "end_date": None,
                "travel_mode": "walking",
                "stops": [],
                "days": [],
                "unassigned_ids": [],
                "route_status": "none",
                "routes": [],
                "weather": {},
                "notices": [],
                "route_cache": {},
            }
            db.add(
                ItineraryTable(
                    id=key, owner=owner, revision=1, document_json=dump(doc), created_at=now
                )
            )
            workspace = db.get(ItineraryWorkspaceTable, owner)
            if workspace:
                workspace.current_id = key
            else:
                db.add(ItineraryWorkspaceTable(owner=owner, current_id=key))
        return self.get(owner, key)

    def edit(self, owner, key, body):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            doc = self.document(row, True)
            values = body.model_dump(mode="json", exclude_none=True, exclude={"version"})
            day_keys = dates(
                values.get("start_date", doc["start_date"]), values.get("end_date", doc["end_date"])
            )
            old_days = {d["date"]: d["stop_ids"] for d in doc["days"]}
            doc.update(values)
            doc["days"] = [{"date": day, "stop_ids": old_days.get(day, [])} for day in day_keys]
            scheduled = {key for d in doc["days"] for key in d["stop_ids"]}
            doc["unassigned_ids"] = [s["id"] for s in doc["stops"] if s["id"] not in scheduled]
            self.write(db, row, changed(doc), body.version)
        return self.get(owner, key)

    def add(self, owner, key, card):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            doc = self.document(row, True)
            old = next((s for s in doc["stops"] if s["place"]["id"] == card["place"]["id"]), None)
            if old:
                return {"itinerary": self.document(row), "stop_id": old["id"], "added": False}
            if len(doc["stops"]) >= 60:
                fail("stop_limit", "一个行程最多收集60个地点。")
            stop = {
                "id": str(uuid4()),
                "place": copy.deepcopy(card["place"]),
                "experience": card.get("experience", ""),
                "added_at": datetime.now(UTC).isoformat(),
            }
            doc["stops"].append(stop)
            doc["unassigned_ids"].append(stop["id"])
            self.write(db, row, changed(doc))
            stop_id = stop["id"]
        return {"itinerary": self.get(owner, key), "stop_id": stop_id, "added": True}

    def remove(self, owner, key, stop_id, version):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            doc = self.document(row, True)
            if not any(s["id"] == stop_id for s in doc["stops"]):
                fail("stop_not_found", "地点已不在行程中。", 404)
            doc["stops"] = [s for s in doc["stops"] if s["id"] != stop_id]
            doc["unassigned_ids"] = [v for v in doc["unassigned_ids"] if v != stop_id]
            for day in doc["days"]:
                day["stop_ids"] = [v for v in day["stop_ids"] if v != stop_id]
            self.write(db, row, changed(doc), version)
        return self.get(owner, key)

    def transfer(self, owner, key, stop_id, body):
        if key == body.target_id:
            return {"itinerary": self.get(owner, key)}
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            source, target = self.owned(db, owner, key), self.owned(db, owner, body.target_id)
            doc, dest = self.document(source, True), self.document(target, True)
            stop = next((s for s in doc["stops"] if s["id"] == stop_id), None)
            if stop is None:
                fail("stop_not_found", "地点已不在原行程中。", 404)
            if not any(s["place"]["id"] == stop["place"]["id"] for s in dest["stops"]):
                if len(dest["stops"]) >= 60:
                    fail("stop_limit", "目标行程已收集60个地点。")
                dest["stops"].append(stop)
                dest["unassigned_ids"].append(stop_id)
                self.write(db, target, changed(dest))
            doc["stops"] = [s for s in doc["stops"] if s["id"] != stop_id]
            doc["unassigned_ids"] = [v for v in doc["unassigned_ids"] if v != stop_id]
            for day in doc["days"]:
                day["stop_ids"] = [v for v in day["stop_ids"] if v != stop_id]
            self.write(db, source, changed(doc), body.version)
        return {"itinerary": self.get(owner, body.target_id)}

    def order(self, owner, key, body):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            doc = self.document(row, True)
            days = [d.model_dump(mode="json") for d in body.days]
            if [d["date"] for d in days] != dates(doc["start_date"], doc["end_date"]):
                fail("invalid_days", "请先确定日期，再按这些日期安排地点。")
            ids = [v for d in days for v in d["stop_ids"]] + body.unassigned_ids
            if len(ids) != len(set(ids)) or set(ids) != {s["id"] for s in doc["stops"]}:
                fail("invalid_stop_order", "安排须完整包含当前地点，且不能重复。")
            doc.update(days=days, unassigned_ids=body.unassigned_ids)
            self.write(db, row, changed(doc), body.version)
        return self.get(owner, key)

    def commit_generation(self, owner, key, expected, result):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            self.write(db, row, result, expected)
        return self.get(owner, key)

    def claim_generation(self, owner, key, body):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            row = self.owned(db, owner, key)
            doc = self.document(row, True)
            if doc.get("last_generation_request") == body.request_id:
                return doc, True
            if body.request_id in doc.get("generation_attempts", []):
                fail("generation_already_attempted", "这次生成已尝试，请查看实际状态。", 409)
            if row.revision != body.version:
                fail("itinerary_changed", "行程已变化，请刷新后继续。", 409)
            since = doc.get("generating_since")
            if since and datetime.now(UTC).timestamp() - since < 100:
                fail("generation_busy", "当前路线仍在生成，请稍候。", 409)
            if not doc["start_date"] or not doc["stops"]:
                fail("itinerary_not_ready", "请先收集地点并确定出行日期。")
            doc["generation_attempts"] = (doc.get("generation_attempts", []) + [body.request_id])[
                -32:
            ]
            doc["generating_since"] = datetime.now(UTC).timestamp()
            self.write(db, row, doc, body.version)
        return self.get(owner, key, True), False

    def adopt(self, guest, user):
        with self.factory.begin() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            db.execute(
                update(ItineraryTable).where(ItineraryTable.owner == guest).values(owner=user)
            )
            latest = db.scalar(
                select(ItineraryTable.id)
                .where(ItineraryTable.owner == user)
                .order_by(ItineraryTable.created_at.desc(), ItineraryTable.id)
            )
            current = db.get(ItineraryWorkspaceTable, user)
            if current:
                current.current_id = latest
            else:
                db.add(ItineraryWorkspaceTable(owner=user, current_id=latest))
            old = db.get(ItineraryWorkspaceTable, guest)
            if old:
                db.delete(old)
