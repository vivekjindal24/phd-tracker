"""Filtered lists as tables for the export service (app/routers/list_exports.py): the same
rows as the page, nothing more."""

import pytest

from app.enums import MODULE_KEYS
from tests.conftest import auth
from tests.test_list_filters import PAGED, meeting  # noqa: F401  (fixture)
from tests.test_publications import enable


async def _get(client, user, path: str, **params):
    return await client.get(f"/api/v1/{path}", headers=auth(user.id), params=params)


@pytest.mark.parametrize("path", PAGED)
async def test_every_list_exports_what_the_page_shows(client, session, world, meeting, path):  # noqa: F811
    await enable(session, *MODULE_KEYS)
    reader = world.meera if path == "documents" else world.research_office
    page = await _get(client, reader, path)
    table = await _get(client, reader, f"internal/lists/{path}")
    assert table.status_code == 200, table.text
    body = table.json()
    assert len(body["rows"]) == len(page.json())
    assert all(len(row) == len(body["columns"]) for row in body["rows"])
    assert table.headers["X-Total-Count"] == page.headers["X-Total-Count"]
    assert body["generated_by"] == reader.full_name


async def test_export_keeps_scope_filters_and_sort(client, world):
    office = world.research_office

    async def names(user, **params) -> list[str]:
        res = await _get(client, user, "internal/lists/scholars", **params)
        assert res.status_code == 200, res.text
        return [row[0] for row in res.json()["rows"]]

    everyone = await names(office)
    assert await names(office, sort="-name") == sorted(everyone, reverse=True)
    assert len(await names(office, q="phd-a1-001")) == 1
    # A head exports their own department's scholars, never the university's.
    listed = await _get(client, world.hod_b1, "scholars")
    assert len(await names(world.hod_b1)) == len(listed.json()) < len(everyone)
    bad = await _get(client, office, "internal/lists/scholars", sort="nope")
    assert bad.status_code == 422


async def test_export_respects_modules_and_permissions(client, world):
    office = world.research_office
    off = await _get(client, office, "internal/lists/publications")  # module is off
    assert off.status_code == 404 and off.json()["error"]["code"] == "module_disabled"
    assert (await _get(client, office, "internal/lists/audit-log")).status_code == 200
    assert (await _get(client, world.scholar_a1, "internal/lists/audit-log")).status_code == 403
    assert (await _get(client, world.scholar_a1, "internal/lists/nothing")).status_code == 404
