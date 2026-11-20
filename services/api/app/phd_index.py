"""The university's own index of the PhD file (PRD F17, part 4): its rows, in its order and
numbering, each filled from Anveshan's records. A row's sources are a whole annexure
("annexure:viva"), one generated form with its signed scan ("form:registration_notice"), or
one uploaded paper ("paper:decisions.drc_minutes"). Each source fills one row only; whatever
the index places nowhere is printed after its rows, under Anveshan's heading, so no record is
left out. With no index set the file keeps Anveshan's annexures.

Applied only when the file is printed: the screens keep Anveshan's annexures, where each paper
is uploaded (signed_copies)."""

from datetime import date
from typing import Any

from app.enums import DOCUMENT_KINDS, PHD_FORMS
from app.phd_file import ANNEXURES, EXAMINER_PAPERS, NOT_IN_USE, NOT_ON_RECORD, NOT_SHOWN

NOT_HELD = "Not held in Anveshan"

# The forms each annexure prints, and the papers uploaded to it that no form stands for.
FORMS: dict[str, tuple[str, ...]] = {
    "supervision": ("appointment", "co_appointment"),
    "advisory_committee": ("committee_formation",),
    "coursework": ("clearance",),
    "comprehensive": ("comprehensive",),
    "registration_seminar": (
        "registration_notice",
        "registration_report",
        "registration_attendance",
    ),
    "progress": ("progress_notice", "progress_attendance"),
    "pre_synopsis_seminar": (
        "pre_synopsis_notice",
        "pre_synopsis_report",
        "pre_synopsis_attendance",
    ),
    "submission": ("submission",),
    "viva": ("viva_approval", "viva_notice", "viva_report", "viva_attendance"),
}
PAPERS: dict[str, tuple[str, ...]] = {
    "coursework": ("mark_sheet",),
    "decisions": ("drc_minutes", "drc_notice"),
    "submission": ("fee_due", "corrections"),
    "examiners": EXAMINER_PAPERS,
    "viva": ("viva_board", "viva_examiner_email"),
}
TITLES = {key: title for key, title, _ in ANNEXURES}


def sources() -> list[dict[str, str]]:
    """Every source a row may draw on, grouped by annexure, for the settings screen."""
    out = []
    for key, title in TITLES.items():
        out.append({"key": f"annexure:{key}", "label": f"All of: {title}", "group": title})
        out += [
            {"key": f"form:{f}", "label": f"{PHD_FORMS[f]} (form)", "group": title}
            for f in FORMS.get(key, ())
        ]
        out += [
            {"key": f"paper:{key}.{p}", "label": f"{DOCUMENT_KINDS[p]} (uploaded)", "group": title}
            for p in PAPERS.get(key, ())
        ]
    return out


SOURCES = frozenset(s["key"] for s in sources())


def _annexure_of(source: str) -> str:
    kind, _, name = source.partition(":")
    if kind == "form":
        return next(k for k, forms in FORMS.items() if name in forms)
    return name.partition(".")[0]


def problems(index: list[dict[str, Any]]) -> list[str]:
    """What is wrong with an index: an unknown source, one placed in two rows, or a whole
    annexure in one row while a form or paper of it is in another (it would print twice)."""
    seen: set[str] = set()
    out = []
    for n, row in enumerate(index, start=1):
        for s in row["sources"]:
            if s not in SOURCES:
                out.append(f"row {n}: no such source {s!r}")
                continue
            if s in seen:
                out.append(f"row {n}: {s} is already in an earlier row")
            seen.add(s)
    whole = {s.partition(":")[2] for s in seen if s.startswith("annexure:")}
    for s in sorted(seen - {f"annexure:{w}" for w in whole}):
        if _annexure_of(s) in whole:
            out.append(f"{s} is part of annexure:{_annexure_of(s)}, which a row takes whole")
    return out


def _papers_of(entry: dict[str, Any], form: dict[str, Any], first: bool) -> list[dict[str, Any]]:
    """The uploaded papers that go with a form: the paper standing for it, the one of its own
    name, and an entry's signed copy with its first form."""
    wanted = {form.get("paper"), form["key"]} | ({"signed_copy"} if first else set())
    return [p for p in entry["papers"] if p["kind"] in wanted]


def arrange(annexures: list[dict[str, Any]], index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The file's parts as the university's index lists them, then whatever it left out.
    `annexures`: phd_file.build with the signed copies attached."""
    if not index:
        return annexures
    by_key = {a["key"]: a for a in annexures}
    taken: dict[int, set[Any]] = {}  # per entry: "all", ("form", key), ("paper", kind)
    shown: set[int] = set()

    def take(e: dict[str, Any], *parts: Any) -> None:
        taken.setdefault(id(e), set()).update(parts)
        shown.add(id(e))

    rows = []
    for n, row in enumerate(index, start=1):
        entries: list[dict[str, Any]] = []
        notes: list[str | None] = []
        for source in row["sources"]:
            kind, _, name = source.partition(":")
            if kind == "annexure":
                notes.append(by_key[name]["note"])
                for e in by_key[name]["entries"]:
                    entries.append(e)
                    take(e, "all")
            elif kind == "form":
                for key in (k for k, forms in FORMS.items() if name in forms):
                    notes.append(by_key[key]["note"])
                    for e in by_key[key]["entries"]:
                        for i, f in enumerate(e["forms"]):
                            if f["key"] == name:
                                papers = _papers_of(e, f, i == 0)
                                entries.append({**e, "forms": [f], "papers": papers})
                                take(e, ("form", name), *(("paper", p["kind"]) for p in papers))
            else:
                key, _, paper = name.partition(".")
                notes.append(by_key[key]["note"])
                for e in by_key[key]["entries"]:
                    papers = [p for p in e["papers"] if p["kind"] == paper and p.get("copy")]
                    if papers:
                        entries.append({**e, "forms": [], "papers": papers})
                        take(e, ("paper", paper))
        entries.sort(key=lambda e: e["date"] or date.max)
        hidden = next((x for x in notes if x in (NOT_SHOWN, NOT_IN_USE)), None)
        rows.append(_part(f"row_{n}", row["title"], entries, hidden, bool(row["sources"])))

    for a in annexures:  # what the index placed nowhere, so that nothing is left out
        rest = []
        for e in a["entries"]:
            t = taken.get(id(e), set())
            if "all" in t:
                continue
            forms = [f for f in e["forms"] if ("form", f["key"]) not in t]
            papers = [p for p in e["papers"] if ("paper", p["kind"]) not in t]
            if id(e) in shown and not forms and not any(p.get("copy") for p in papers):
                continue
            rest.append({**e, "forms": forms, "papers": papers})
        if rest:
            rows.append(_part(a["key"], a["title"], rest, None, True))
    return rows


def _part(
    key: str, title: str, entries: list[dict[str, Any]], hidden: str | None, sourced: bool
) -> dict[str, Any]:
    dates = [e["date"] for e in entries if e["date"]]
    note = None if entries else hidden or (NOT_ON_RECORD if sourced else NOT_HELD)
    return {
        "key": key,
        "title": title,
        "date": min(dates) if dates else None,
        "entries": entries,
        "note": note,
    }
