from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from app.config import get_settings

settings = get_settings()

token_blacklist: set[str] = set()

login_failure_tracker: dict[str, dict] = {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.token_expire_days)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def is_token_blacklisted(token: str) -> bool:
    return token in token_blacklist


def blacklist_token(token: str) -> None:
    token_blacklist.add(token)


def record_login_failure(investor_code: str) -> tuple[bool, Optional[datetime]]:
    now = datetime.utcnow()
    tracker = login_failure_tracker.get(investor_code)

    if tracker is None:
        login_failure_tracker[investor_code] = {"count": 1, "locked_until": None}
        return False, None

    locked_until = tracker.get("locked_until")
    if locked_until and now < locked_until:
        return True, locked_until

    if locked_until and now >= locked_until:
        tracker["count"] = 1
        tracker["locked_until"] = None
        return False, None

    tracker["count"] += 1

    if tracker["count"] >= 5:
        lock_until = now + timedelta(minutes=15)
        tracker["locked_until"] = lock_until
        return True, lock_until

    return False, None


def clear_login_failure(investor_code: str) -> None:
    if investor_code in login_failure_tracker:
        del login_failure_tracker[investor_code]


def is_account_locked(investor_code: str) -> tuple[bool, Optional[datetime]]:
    tracker = login_failure_tracker.get(investor_code)
    if not tracker:
        return False, None

    locked_until = tracker.get("locked_until")
    if locked_until and datetime.utcnow() < locked_until:
        return True, locked_until

    if locked_until and datetime.utcnow() >= locked_until:
        del login_failure_tracker[investor_code]
        return False, None

    return False, None
