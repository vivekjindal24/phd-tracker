"""The permission matrix (SECURITY.md §3) enforced across the whole API. These walk every route
the app publishes, so a new route is covered the moment it exists. Per-record rules stay in each
module's own tests: fake ids stop at 403 here."""

import re

import pytest

from app.enums import MODULE_KEYS
from app.main import app
from tests.conftest import auth
from tests.test_publications import enable

API = "/api/v1"
ROLES = frozenset(
    {
        "scholar_a1",
        "sup_b1",
        "meera",  # supervisor + head + admin of A1
        "hod_b1",
        "dean_a",
        "admin_a1",
        "root_admin",
        "research_office",
        "exam_office",
        "library",
    }
)
ADMINS = frozenset({"meera", "admin_a1", "root_admin"})
OFFICES = frozenset({"exam_office", "library"})
HEADS = frozenset({"hod_b1", "dean_a"})

# Reached without a login: add here only on purpose. The rest is a 401.
PUBLIC = frozenset(
    {
        "GET /healthz",
        "GET /branding",
        "GET /branding/logo",
        "GET /verify/{token}",
        "POST /auth/login",
        "POST /auth/refresh",
        "POST /auth/logout",
        "POST /auth/forgot-password",
        "POST /auth/set-password",
        "GET /auth/sso/providers",
        "GET /auth/sso/{provider}/start",
        "GET /auth/sso/{provider}/callback",
        "POST /auth/sso/exchange",
        "POST /internal/cron/daily",  # its own X-Cron-Secret
    }
)
MODULE_OF_TAG = {
    "publications": "publications",
    "conferences": "conferences",
    "documents": "documents",
    "thesis": "documents",
    "coursework": "coursework",
    "admissions": "admissions",
    "fellowships": "fellowships",
    "projects": "projects",
    "ledger": "ledger",
}
# List route -> roles the matrix refuses; every other role gets 200, filtered by scope.
LIST_REFUSED = {
    "/users": OFFICES,
    "/meetings": OFFICES,
    "/reports": OFFICES,
    "/seminars": OFFICES,
    "/todos": OFFICES,
    "/fellowships": OFFICES,
    "/projects": OFFICES,
    "/milestones": {"library"},
    "/courses": {"library"},
    "/publications": {"exam_office"},
    "/conferences": {"exam_office"},
    "/admissions": {"scholar_a1", "sup_b1", *OFFICES},
    "/leadership": {"scholar_a1", "sup_b1", *OFFICES},
    "/documents": {"hod_b1", "dean_a", "admin_a1", "root_admin", "research_office", *OFFICES},
    "/no-dues/mine": ROLES - {"scholar_a1"},
}
# Create route -> roles allowed. An empty body shows the guard: 403 refused, 422 let through.
CREATE_ALLOWED = {
    "/org-units": {"root_admin"},
    "/users": ADMINS,
    "/role-assignments": ADMINS,
    "/meetings": {"scholar_a1", "sup_b1", "meera"},
    "/reports": {"scholar_a1"},
    "/milestones": {*ADMINS, "research_office"},
    "/publications": {"scholar_a1"},
    "/conferences": {"scholar_a1"},
    "/documents": {"scholar_a1"},
    "/theses": {"scholar_a1"},
    "/courses": {*ADMINS, "exam_office"},
    "/enrolments": {"exam_office"},
    "/clearances": {"exam_office"},
    "/admissions": {*ADMINS, "research_office"},
    "/fellowships": {*ADMINS, "research_office"},
    "/projects": {*ADMINS, "research_office"},
}


def operations() -> list[tuple[str, str, str]]:
    return [
        (method.upper(), path.removeprefix(API), (op.get("tags") or ["-"])[0])
        for path, item in app.openapi()["paths"].items()
        for method, op in item.items()
        if method in ("get", "post", "put", "patch", "delete")
    ]


def fake_ids(path: str) -> str:
    return API + re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000001", path)


async def test_every_route_but_the_public_ones_needs_a_login(client, session):
    await enable(session, *MODULE_KEYS)  # a disabled module answers before the login check
    refused = set()
    for method, path, _ in operations():
        res = await client.request(method, fake_ids(path), json={})
        if res.status_code == 401:
            refused.add(f"{method} {path}")
    assert {f"{m} {p}" for m, p, _ in operations()} - refused == PUBLIC


async def test_every_route_of_a_disabled_module_is_404(client, world):
    seen = set()
    for method, path, tag in operations():
        if tag not in MODULE_OF_TAG:
            continue
        seen.add(MODULE_OF_TAG[tag])
        res = await client.request(
            method, fake_ids(path), json={}, headers=auth(world.root_admin.id)
        )
        assert res.status_code == 404, (method, path, res.text)
        assert res.json()["error"]["code"] == "module_disabled", (method, path)
    assert seen == set(MODULE_KEYS)


@pytest.mark.parametrize("path", LIST_REFUSED)
async def test_lists_follow_the_matrix(client, session, world, path):
    await enable(session, *MODULE_KEYS)
    for role in sorted(ROLES):
        res = await client.get(f"{API}{path}", headers=auth(getattr(world, role).id))
        expected = 403 if role in LIST_REFUSED[path] else 200
        assert res.status_code == expected, (role, path, res.text)


@pytest.mark.parametrize("path", CREATE_ALLOWED)
async def test_creates_follow_the_matrix(client, session, world, path):
    await enable(session, *MODULE_KEYS)
    for role in sorted(ROLES):
        res = await client.post(f"{API}{path}", json={}, headers=auth(getattr(world, role).id))
        expected = 422 if role in CREATE_ALLOWED[path] else 403
        assert res.status_code == expected, (role, path, res.text)
