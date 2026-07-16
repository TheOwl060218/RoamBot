from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe


def new_token() -> str:
    return token_urlsafe(32)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SessionSecrets:
    session_token: str
    session_hash: str
    csrf_token: str
    csrf_hash: str

    @classmethod
    def create(cls) -> "SessionSecrets":
        session_token = new_token()
        csrf_token = new_token()
        return cls(
            session_token=session_token,
            session_hash=hash_token(session_token),
            csrf_token=csrf_token,
            csrf_hash=hash_token(csrf_token),
        )
