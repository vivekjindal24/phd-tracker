"""Time-based one-time codes for authenticator apps (RFC 6238: HMAC-SHA1, 30 s, 6 digits),
and the one-time recovery codes given at setup. Standard library only."""

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1  # accept the step before and after: phones' clocks drift
RECOVERY_CODES = 8
ISSUER = "Anveshan"


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def step_of(at: float) -> int:
    return int(at // STEP_SECONDS)


def _code_at(secret: str, step: int) -> str:
    digest = hmac.new(base64.b32decode(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def code(secret: str, at: float) -> str:
    return _code_at(secret, step_of(at))


def matching_step(secret: str, given: str, at: float, after: int | None) -> int | None:
    """The time step `given` is the code for, if it is within the window and later than
    `after` (the last step this person used: a code works once)."""
    for step in range(step_of(at) - WINDOW, step_of(at) + WINDOW + 1):
        if (after is None or step > after) and hmac.compare_digest(_code_at(secret, step), given):
            return step
    return None


def otpauth_uri(secret: str, email: str) -> str:
    label = quote(f"{ISSUER}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={ISSUER}&digits={DIGITS}&period=30"


def new_recovery_codes() -> list[str]:
    """Ten random characters each (50 bits): unguessable, so a plain sha256 is enough at rest."""
    return [secrets.token_hex(5) for _ in range(RECOVERY_CODES)]


def hash_recovery(code_: str) -> str:
    return hashlib.sha256(code_.strip().lower().encode()).hexdigest()
