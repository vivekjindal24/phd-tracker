"""Org tree editing and university settings — root admin only (PRD F1, F3, F4; Flow 5)."""

import pytest
from sqlalchemy import select

from app.errors import ApiError
from app.models import OrgUnit
from app.modules import require_module
from tests.conftest import auth


async def test_everyone_reads_the_tree_in_path_order(client, world):
    res = await client.get("/api/v1/org-units", headers=auth(world.scholar_b1.id))
    assert res.status_code == 200
    paths = [u["path"] for u in res.json()]
    assert paths == sorted(paths) and paths[0] == "tu" and "tu.sa.a1" in paths


async def test_root_admin_adds_unit_under_parent(client, world):
    res = await client.post(
        "/api/v1/org-units",
        json={
            "parent_id": str(world.school_b.id),
            "name": "Dept B2",
            "kind": "Department",
            "code": "B-2",
        },
        headers=auth(world.root_admin.id),
    )
    assert res.status_code == 201
    assert res.json()["path"] == "tu.sb.b_2"


async def test_non_root_admin_cannot_edit_tree(client, world):
    res = await client.post(
        "/api/v1/org-units",
        json={"parent_id": str(world.a1.id), "name": "Lab", "kind": "Lab", "code": "LAB"},
        headers=auth(world.admin_a1.id),
    )
    assert res.status_code == 403


async def test_duplicate_code_is_409(client, world):
    res = await client.post(
        "/api/v1/org-units",
        json={"parent_id": str(world.root.id), "name": "Again", "kind": "School", "code": "SA"},
        headers=auth(world.root_admin.id),
    )
    assert (res.status_code, res.json()["error"]["code"]) == (409, "duplicate_unit_code")


async def test_moving_a_school_rewrites_descendant_paths_and_scope(client, world, session):
    res = await client.patch(
        f"/api/v1/org-units/{world.a1.id}",
        json={"parent_id": str(world.school_b.id)},
        headers=auth(world.root_admin.id),
    )
    assert res.status_code == 200 and res.json()["path"] == "tu.sb.a1"
    # Dean of School A no longer sees A1's scholars; HoD of B1 still doesn't (sibling).
    from tests.test_scope import visible_rolls

    assert await visible_rolls(session, world.dean_a) == {"PHD-A2-001"}


async def test_cannot_move_unit_inside_itself(client, world):
    res = await client.patch(
        f"/api/v1/org-units/{world.school_a.id}",
        json={"parent_id": str(world.a1.id)},
        headers=auth(world.root_admin.id),
    )
    assert res.json()["error"]["code"] == "invalid_move"


async def test_delete_only_empty_units(client, world, session):
    busy = await client.delete(
        f"/api/v1/org-units/{world.a1.id}", headers=auth(world.root_admin.id)
    )
    assert busy.json()["error"]["code"] == "unit_not_empty"
    empty = await client.post(
        "/api/v1/org-units",
        json={"parent_id": str(world.root.id), "name": "Empty", "kind": "School", "code": "EMPTY"},
        headers=auth(world.root_admin.id),
    )
    unit_id = empty.json()["id"]
    gone = await client.delete(f"/api/v1/org-units/{unit_id}", headers=auth(world.root_admin.id))
    assert gone.status_code == 204
    row = await session.get(OrgUnit, empty.json()["id"])
    assert row.deleted_at is not None  # soft delete only


async def test_root_cannot_be_deleted(client, world):
    res = await client.delete(
        f"/api/v1/org-units/{world.root.id}", headers=auth(world.root_admin.id)
    )
    assert res.json()["error"]["code"] == "cannot_delete_root"


async def test_settings_readable_by_all_with_default_chains(client, world):
    res = await client.get("/api/v1/settings", headers=auth(world.scholar_a1.id))
    body = res.json()
    assert body["co_supervision"] == "off"
    assert [s["kind"] for s in body["chains"]["publication"]] == [
        "supervisor",
        "library",
        "research_office",
    ]
    assert body["modules"]["ledger"] is False
    assert body["email_configured"] is False  # conftest clears SMTP_*


@pytest.mark.parametrize(
    ("method", "url", "payload"),
    [
        ("patch", "/api/v1/settings", {"co_supervision": "view"}),
        ("put", "/api/v1/settings/modules/ledger", {"enabled": True}),
        ("put", "/api/v1/settings/chains/publication", {"steps": [{"kind": "library"}]}),
    ],
)
async def test_only_root_admin_changes_settings(client, world, method, url, payload):
    denied = await getattr(client, method)(url, json=payload, headers=auth(world.meera.id))
    assert denied.status_code == 403
    ok = await getattr(client, method)(url, json=payload, headers=auth(world.root_admin.id))
    assert ok.status_code == 200


@pytest.mark.parametrize("steps", [[], [{"kind": "registrar"}], [{"kind": "library"}] * 9])
async def test_chain_validation(client, world, steps):
    res = await client.put(
        "/api/v1/settings/chains/progress_report",
        json={"steps": steps},
        headers=auth(world.root_admin.id),
    )
    assert res.status_code == 422


async def test_module_guard_follows_switch(client, world, session):
    guard = require_module("ledger")
    with pytest.raises(ApiError) as exc:
        await guard(session)
    assert (exc.value.status, exc.value.code) == (404, "module_disabled")
    await client.put(
        "/api/v1/settings/modules/ledger", json={"enabled": True}, headers=auth(world.root_admin.id)
    )
    await guard(session)  # enabled: no error
    me = (await client.get("/api/v1/auth/me", headers=auth(world.scholar_a1.id))).json()
    assert me["modules"]["ledger"] is True


async def test_settings_changes_are_audited(client, world, session):
    from app.models import AuditLog

    await client.patch(
        "/api/v1/settings", json={"co_supervision": "approve"}, headers=auth(world.root_admin.id)
    )
    row = await session.scalar(select(AuditLog).where(AuditLog.table_name == "settings"))
    assert (row.prev["co_supervision"], row.data["co_supervision"]) == ("off", "approve")
