"""Column sorting on paged lists (app/sorting.py): server-side, whitelisted, stable across pages."""

import pytest

from app.enums import MODULE_KEYS, STAGES
from app.main import app
from tests.conftest import auth
from tests.test_list_filters import PAGED, meeting  # noqa: F401  (fixture)
from tests.test_publications import enable


async def _get(client, user, path: str, **params):
    return await client.get(f"/api/v1/{path}", headers=auth(user.id), params=params)


async def _allowed(client, user, path: str) -> list[str]:
    res = await _get(client, user, path, sort="no_such_column")
    assert res.status_code == 422, f"{path}: {res.text}"
    error = res.json()["error"]
    assert error["code"] == "invalid_sort"
    return error["details"]["allowed"]


def test_every_paged_list_takes_a_sort():
    paths = app.openapi()["paths"]
    for name in PAGED:
        params = {p["name"] for p in paths[f"/api/v1/{name}"]["get"]["parameters"]}
        assert "sort" in params, name


@pytest.mark.parametrize("path", PAGED)
async def test_every_allowed_key_sorts_both_ways(client, session, world, meeting, path):  # noqa: F811
    await enable(session, *MODULE_KEYS)
    # Drafts are read by their scholar and supervisors, not the offices.
    reader = world.meera if path == "documents" else world.research_office
    keys = await _allowed(client, reader, path)
    assert keys, path
    for key in keys:
        for sort in (key, f"-{key}"):
            res = await _get(client, reader, path, sort=sort)
            assert res.status_code == 200, f"{path} sort={sort}: {res.text}"


async def test_scholars_sort_by_column_and_direction(client, world):
    office = world.research_office

    async def names(sort: str) -> list[str]:
        res = await _get(client, office, "scholars", sort=sort)
        assert res.status_code == 200, res.text
        return [s["full_name"] for s in res.json()]

    ascending = await names("name")
    assert ascending == sorted(ascending) and await names("-name") == ascending[::-1]
    # Stages sort in the order a scholar moves through them, not alphabetically.
    res = await _get(client, office, "scholars", sort="stage")
    ranks = [STAGES.index(s["stage"]) for s in res.json()]
    assert ranks == sorted(ranks)


async def test_pages_continue_the_same_order(client, world):
    office = world.research_office
    whole = [s["id"] for s in (await _get(client, office, "scholars", sort="stage")).json()]
    paged: list[str] = []
    while len(paged) < len(whole):
        res = await _get(client, office, "scholars", sort="stage", limit=2, offset=len(paged))
        paged += [s["id"] for s in res.json()]
    assert paged == whole  # equal stages tie-break on id: no row repeats or goes missing


async def test_sort_text_is_validated(client, world):
    res = await _get(client, world.research_office, "scholars", sort="name; drop table")
    assert res.status_code == 422
