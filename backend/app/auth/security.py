from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings

# NOTE: deliberately using the `bcrypt` package directly rather than
# passlib's CryptContext. passlib 1.7.4 (pinned in requirements.txt) reads
# bcrypt.__about__.__version__ to detect the backend version, which no
# longer exists in bcrypt>=4.1 - this crashes every hash/verify call with
# an AttributeError, and previously caused every single login to fail
# (the frontend swallowed that 500 error into a generic "Identifiants
# incorrects" message, making it look like a wrong password rather than a
# broken hashing backend). Calling bcrypt directly avoids the passlib
# version-detection code path entirely.

BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores bytes beyond this - truncate explicitly to avoid surprises


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
