"""AI-drafted seminar to-do points (PRD F15) over any OpenAI-compatible chat endpoint —
Gemini in dev/test, a local Ollama model in production. Only the graders' comment text is
sent: no names, roll numbers or marks. The supervisor always reviews the draft."""

import asyncio
import json
import logging

import httpx

from app.config import settings
from app.enums import TODO_PART_LABELS, TODO_PARTS

log = logging.getLogger("anveshan.ai")
TIMEOUT_S = 45
BUSY_STATUSES = frozenset({429, 503})  # free tiers shed load; one retry usually succeeds
RETRY_DELAY_S = 2.0
MAX_POINTS = 15
MAX_POINT_CHARS = 300

SYSTEM_PROMPT = f"""You help a PhD supervisor turn progress-seminar feedback into a to-do list.
You receive comments written by panel members about one scholar's work.

Rules:
- Turn every concrete, actionable suggestion into one short imperative point
  (for example "Add an ablation study comparing the two encoders").
- Merge duplicates raised by several panel members into one point.
- Ignore praise and anything that is not a change the scholar should make.
- Do not invent suggestions that are not in the comments.
- At most {MAX_POINTS} points, each under {MAX_POINT_CHARS} characters.
- Tag each point with exactly one part from this list (use the id):
{chr(10).join(f"  {pid}: {label}" for pid, label in TODO_PART_LABELS.items())}

Reply with JSON only, in this exact shape:
{{"points": [{{"part": "<part id>", "text": "<point>"}}]}}"""


class AiUnavailable(Exception):
    """The AI could not produce a usable draft; the supervisor writes points by hand."""


def available() -> bool:
    return settings.ai is not None


def _parse(content: str) -> list[dict[str, str]]:
    text = content.strip()
    if text.startswith("```"):  # some models wrap JSON in a fence despite instructions
        text = text.strip("`").removeprefix("json").strip()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AiUnavailable("the AI reply was not valid JSON") from exc
    items = raw.get("points") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise AiUnavailable("the AI reply had no list of points")
    points = []
    for item in items[:MAX_POINTS]:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        part = item.get("part") if item.get("part") in TODO_PARTS else "other"
        points.append({"part": part, "text": str(item["text"]).strip()[:MAX_POINT_CHARS]})
    return points


async def suggest_points(
    comments: list[str], transport: httpx.AsyncBaseTransport | None = None
) -> list[dict[str, str]]:
    ai = settings.ai
    if ai is None:
        raise AiUnavailable("AI is not configured on this server")
    feedback = "\n\n".join(
        f"Comment {i}:\n{c.strip()}" for i, c in enumerate(comments, 1) if c.strip()
    )
    if not feedback:
        return []
    body = {
        "model": ai.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": feedback},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as client:
            for attempt in (1, 2):
                res = await client.post(
                    f"{ai.base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {ai.api_key}"},
                )
                if res.status_code not in BUSY_STATUSES or attempt == 2:
                    break
                log.info("AI busy (HTTP %s); retrying once", res.status_code)
                await asyncio.sleep(RETRY_DELAY_S)
    except httpx.HTTPError as exc:
        log.warning("AI request failed: %s", exc)
        raise AiUnavailable("the AI service could not be reached") from exc
    if res.status_code != 200:
        log.warning("AI returned HTTP %s: %s", res.status_code, res.text[:300])
        raise AiUnavailable(f"the AI service answered {res.status_code}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AiUnavailable("the AI reply had an unexpected shape") from exc
    return _parse(content or "")
