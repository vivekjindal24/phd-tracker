"""Input Postgres cannot store or compare is the caller's mistake: 422, never a 500."""

import pytest

from tests.conftest import auth
from tests.test_publications import enable


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/search?q=ab%00cd",
        "/api/v1/users?q=ab%00cd",
        "/api/v1/scholars?q=ab%00cd",
        "/api/v1/faculty?q=ab%00cd",
        "/api/v1/scholars?offset=99999999999999999999",
    ],
)
async def test_unstorable_query_values_are_422(client, world, path):
    res = await client.get(path, headers=auth(world.root_admin.id))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_value"


async def test_malformed_id_in_a_path_is_404(client, world):
    res = await client.get("/api/v1/scholars/not-a-uuid", headers=auth(world.root_admin.id))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


async def test_like_wildcards_are_plain_text_in_search(client, world):
    res = await client.get("/api/v1/search?q=%25%25", headers=auth(world.root_admin.id))
    assert res.status_code == 200
    assert not any(res.json().values())


async def test_library_cannot_read_the_course_catalogue(client, session, world):
    await enable(session, "coursework")
    res = await client.get("/api/v1/courses", headers=auth(world.library.id))
    assert res.status_code == 403


async def test_a_century_long_extension_is_refused(client, world):
    res = await client.post(
        f"/api/v1/scholars/{world.s_a1.id}/time-adjustments",
        headers=auth(world.research_office.id),
        json={"kind": "extension", "start_date": "2026-01-01", "end_date": "2126-01-01"},
    )
    assert res.status_code == 422


async def test_no_dues_needs_the_university_to_require_it(client, session, world):
    await enable(session, "documents")
    res = await client.post("/api/v1/no-dues", headers=auth(world.scholar_a1.id))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "no_dues_not_required"
