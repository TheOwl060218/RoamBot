"""Durable request isolation; no database transaction spans a provider/API call."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from roambot.persistence.tables import Base


class CommandLog(Base):
    __tablename__ = "assistant_commands"
    actor: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    proposal: Mapped[str] = mapped_column(String(36), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommandConflict(ValueError):
    pass


def request_digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class CommandJournal:
    def __init__(self, factory):
        self.factory = factory

    def find(self, actor, request_id):
        with self.factory() as db:
            return db.get(CommandLog, (actor, request_id))

    def reserve(self, actor, body):
        request_id, digest = body["request_id"], request_digest(body)
        try:
            with self.factory.begin() as db:
                row = CommandLog(
                    actor=actor,
                    request_id=request_id,
                    proposal=str(uuid4()),
                    digest=digest,
                    status="planning",
                    data_json=json.dumps({"command": body}),
                    created_at=datetime.now(UTC),
                )
                db.add(row)
                db.flush()
        except IntegrityError:
            return False
        return True

    def get(self, actor, request_id, proposal=None):
        row = self.find(actor, request_id)
        if row is None or (proposal is not None and row.proposal != proposal):
            raise LookupError("操作不存在或不属于当前会话。")
        return row

    def claim(self, actor, request_id):
        with self.factory.begin() as db:
            changed = db.execute(
                update(CommandLog)
                .where(
                    CommandLog.actor == actor,
                    CommandLog.request_id == request_id,
                    CommandLog.status.in_(["planned", "failed"]),
                )
                .values(status="running")
            )
            return changed.rowcount == 1

    def save(self, actor, request_id, status, data):
        with self.factory.begin() as db:
            row = db.get(CommandLog, (actor, request_id))
            row.status, row.data_json = status, json.dumps(data, ensure_ascii=False)

    @staticmethod
    def expired(row):
        created = row.created_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - created > timedelta(hours=1)
