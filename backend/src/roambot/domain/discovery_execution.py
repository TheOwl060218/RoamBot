"""Private immutable messages between discovery workers and the coordinator."""

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchInput:
    identity: str
    revision: int
    sequence: int
    payload_json: str
    fingerprint: str

    @classmethod
    def freeze(cls, identity, revision, sequence, payload):
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        bound = json.dumps([identity, revision, sequence, raw], ensure_ascii=False)
        return cls(identity, revision, sequence, raw, hashlib.sha256(bound.encode()).hexdigest())

    def payload(self):
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class BatchResult:
    batch: BatchInput
    payload_json: str

    @classmethod
    def freeze(cls, batch, payload):
        return cls(batch, json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def payload(self):
        return json.loads(self.payload_json)
