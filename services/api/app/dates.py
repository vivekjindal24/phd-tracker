"""How this university writes a date, everywhere Anveshan writes one: forms, notices, emails,
reminders (here), the PDFs (export service) and the screens (web) — chosen once in Settings
(settings.date_format; owner, 2026-11-22). Month names are fixed English, never the server's
locale, so the three services print exactly the same thing. CSV downloads keep ISO dates
(2026-11-21) so spreadsheets sort them.

The format is read from the settings at most once a minute per process (`refresh`, run before
every request) and at once when the root admin changes it."""

import time
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DEFAULT_DATE_FORMAT, LOCAL_TZ

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
FULL_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
REFRESH_SECONDS = 60

_current = {"format": DEFAULT_DATE_FORMAT, "read_at": 0.0}


def use(fmt: str) -> None:
    _current.update(format=fmt, read_at=time.monotonic())


async def refresh(session: AsyncSession) -> None:
    """Re-read the university's format when the copy here is older than a minute."""
    if time.monotonic() - _current["read_at"] < REFRESH_SECONDS:
        return
    from app.models import Settings  # the models import this module's callers

    use(await session.scalar(select(Settings.date_format)) or DEFAULT_DATE_FORMAT)


def current() -> str:
    return str(_current["format"])


def _local(day: date | datetime) -> date:
    return day.astimezone(LOCAL_TZ).date() if isinstance(day, datetime) else day


def day(value: date | datetime | None, fmt: str | None = None) -> str:
    """A date as the university writes it: "21 Nov 2026", "21/11/2026" …; "—" for none."""
    if value is None:
        return "—"
    d = _local(value)
    dd, mm, yyyy = f"{d.day:02d}", f"{d.month:02d}", f"{d.year:04d}"
    return {
        "d_mon_yyyy": f"{d.day} {MONTHS[d.month - 1]} {yyyy}",
        "d_month_yyyy": f"{d.day} {FULL_MONTHS[d.month - 1]} {yyyy}",
        "dd/mm/yyyy": f"{dd}/{mm}/{yyyy}",
        "dd-mm-yyyy": f"{dd}-{mm}-{yyyy}",
        "dd.mm.yyyy": f"{dd}.{mm}.{yyyy}",
        "yyyy-mm-dd": f"{yyyy}-{mm}-{dd}",
        "mm/dd/yyyy": f"{mm}/{dd}/{yyyy}",
    }[fmt or current()]


def clock(at: datetime) -> str:
    """ "4:30 pm" in India's time."""
    t = at.astimezone(LOCAL_TZ)
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


def when(at: datetime) -> str:
    """ "21 Nov 2026, 4:30 pm": a moment, as the university writes dates."""
    return f"{day(at)}, {clock(at)}"


if __name__ == "__main__":  # the formats, checked: python -m app.dates
    sample = date(2026, 9, 3)
    assert day(sample, "d_mon_yyyy") == "3 Sep 2026"
    assert day(sample, "d_month_yyyy") == "3 September 2026"
    assert day(sample, "dd/mm/yyyy") == "03/09/2026"
    assert day(sample, "mm/dd/yyyy") == "09/03/2026"
    assert day(sample, "yyyy-mm-dd") == "2026-09-03"
    assert day(None) == "—"
    print("ok")
