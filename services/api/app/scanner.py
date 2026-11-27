"""Every upload passes through ClamAV before anyone can open it (owner, 2026-11-27; SECURITY.md
§8). The daemon's INSTREAM command takes the bytes in length-prefixed chunks and answers
"stream: OK" or "stream: <name> FOUND". It fails closed: when the scanner cannot answer, the
upload is refused, never kept unscanned."""

import asyncio
import logging
import socket
import struct
from collections.abc import Iterable

from app import storage
from app.config import settings
from app.errors import ApiError

log = logging.getLogger("anveshan.scanner")
CHUNK = 1 << 20  # what one INSTREAM chunk carries
TIMEOUT_S = 120  # a large PDF on a small server, while the daemon is busy


def unavailable() -> ApiError:
    return ApiError(
        503,
        "scanner_unavailable",
        "Files cannot be checked for viruses right now, so uploads are paused. "
        "Please try again in a few minutes.",
    )


def infected(name: str) -> ApiError:
    log.warning("upload refused: virus %s", name)
    return ApiError(
        422,
        "infected_file",
        f"This file contains a virus ({name}) and was not kept. Scan your computer, then "
        "upload a clean copy.",
    )


def verdict(reply: bytes) -> str | None:
    """None for a clean file, the virus's name for an infected one."""
    text = reply.decode(errors="replace").strip("\0 \r\n")
    if text.endswith(" OK"):
        return None
    if text.endswith(" FOUND"):
        return text.removeprefix("stream: ").removesuffix(" FOUND")
    log.error("scanner answered %r", text)  # e.g. a size limit below MAX_UPLOAD_MB
    raise unavailable()


def _scan(chunks: Iterable[bytes]) -> str | None:
    scanner = settings.scanner
    try:
        with socket.create_connection((scanner.host, scanner.port), timeout=TIMEOUT_S) as sock:
            sock.sendall(b"zINSTREAM\0")
            for chunk in chunks:
                for i in range(0, len(chunk), CHUNK):
                    part = chunk[i : i + CHUNK]
                    sock.sendall(struct.pack(">I", len(part)) + part)
            sock.sendall(struct.pack(">I", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                data = sock.recv(4096)
                if not data:
                    break
                reply += data
    except OSError as exc:
        log.error("scanner unreachable at %s:%s: %s", scanner.host, scanner.port, exc)
        raise unavailable() from exc
    return verdict(reply)


async def scan_bytes(content: bytes) -> None:
    """An upload the API holds in memory (images, import spreadsheets): refused if infected."""
    if name := await asyncio.to_thread(_scan, [content]):
        raise infected(name)


async def scan_object(key: str) -> str | None:
    """A file the browser put straight into storage; the caller removes it if infected."""
    return await asyncio.to_thread(lambda: _scan(storage.object_chunks(key, CHUNK)))
