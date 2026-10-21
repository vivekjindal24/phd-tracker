"""Scoped admin management of users, profiles and roles (PRD F2, Flow 5)."""

from sqlalchemy import select

from app.models import AuditLog, Faculty, RoleAssignment, Scholar
from tests.conftest import auth

NEW_PASSWORD = "initial-passphrase-1"


def scholar_body(unit_id, email="new@x.edu", roll="PHD-NEW-001"):
    return {
        "email": email,
        "full_name": "New Scholar",
        "password": NEW_PASSWORD,
        "scholar": {"unit_id": str(unit_id), "roll_number": roll},
    }


async def test_department_admin_adds_scholar_to_own_department(client, world, session):
    res = await client.post(
        "/api/v1/users", json=scholar_body(world.a1.id), headers=auth(world.admin_a1.id)
    )
    assert res.status_code == 201, res.text
    scholar = await session.scalar(select(Scholar).where(Scholar.roll_number == "PHD-NEW-001"))
    assert scholar.unit_id == world.a1.id
    audit = await session.scalar(
        select(AuditLog).where(AuditLog.table_name == "users", AuditLog.action == "insert")
    )
    assert audit.data["password_hash"] == "[redacted]"
    assert audit.actor_id == world.admin_a1.id


async def test_department_admin_cannot_add_outside_subtree(client, world):
    res = await client.post(
        "/api/v1/users", json=scholar_body(world.b1.id), headers=auth(world.admin_a1.id)
    )
    assert res.status_code == 403


async def test_unit_head_without_admin_role_cannot_add_people(client, world):
    res = await client.post(
        "/api/v1/users", json=scholar_body(world.a2.id), headers=auth(world.hod_a2.id)
    )
    assert res.status_code == 403


async def test_faculty_cap_defaults_from_designation(client, world, session):
    body = {
        "email": "asst@x.edu",
        "full_name": "Asst Prof",
        "password": NEW_PASSWORD,
        "faculty": {"unit_id": str(world.a1.id), "designation": "Assistant Professor"},
    }
    res = await client.post("/api/v1/users", json=body, headers=auth(world.admin_a1.id))
    assert res.status_code == 201
    faculty = await session.scalar(select(Faculty).where(Faculty.user_id == res.json()["id"]))
    assert faculty.max_scholars == 4


async def test_bare_office_account_needs_root_admin(client, world):
    body = {"email": "clerk@x.edu", "full_name": "Clerk", "password": NEW_PASSWORD}
    assert (
        await client.post("/api/v1/users", json=body, headers=auth(world.admin_a1.id))
    ).status_code == 403
    assert (
        await client.post("/api/v1/users", json=body, headers=auth(world.root_admin.id))
    ).status_code == 201


async def test_duplicate_email_and_roll_number_are_named_409s(client, world):
    dup_email = scholar_body(world.a1.id, email="scholar_a1@x.edu")
    res = await client.post("/api/v1/users", json=dup_email, headers=auth(world.root_admin.id))
    assert (res.status_code, res.json()["error"]["code"]) == (409, "duplicate_email")
    dup_roll = scholar_body(world.a1.id, roll="PHD-A1-001")
    res = await client.post("/api/v1/users", json=dup_roll, headers=auth(world.root_admin.id))
    assert (res.status_code, res.json()["error"]["code"]) == (409, "duplicate_roll_number")


async def test_both_profiles_at_once_is_rejected(client, world):
    body = scholar_body(world.a1.id)
    body["faculty"] = {"unit_id": str(world.a1.id), "designation": "Professor"}
    res = await client.post("/api/v1/users", json=body, headers=auth(world.root_admin.id))
    assert res.status_code == 422


async def test_user_listing_is_scoped(client, world):
    res = await client.get("/api/v1/users?limit=200", headers=auth(world.admin_a1.id))
    emails = {u["email"] for u in res.json()}
    assert {"scholar_a1@x.edu", "scholar_a1b@x.edu", "meera@x.edu", "admin_a1@x.edu"} <= emails
    assert "scholar_b1@x.edu" not in emails
    assert "research_office@x.edu" not in emails


async def test_scholar_only_sees_self_in_user_listing(client, world):
    res = await client.get("/api/v1/users", headers=auth(world.scholar_a1.id))
    assert [u["email"] for u in res.json()] == ["scholar_a1@x.edu"]
    other = await client.get(
        f"/api/v1/users/{world.scholar_b1.id}", headers=auth(world.scholar_a1.id)
    )
    assert other.status_code == 403


async def test_admin_grants_hod_in_own_unit_but_not_above(client, world):
    ok = await client.post(
        "/api/v1/role-assignments",
        json={"user_id": str(world.sup_a2.id), "role": "unit_head", "unit_id": str(world.a1.id)},
        headers=auth(world.admin_a1.id),
    )
    assert ok.status_code == 201
    above = await client.post(
        "/api/v1/role-assignments",
        json={
            "user_id": str(world.sup_a2.id),
            "role": "unit_head",
            "unit_id": str(world.school_a.id),
        },
        headers=auth(world.admin_a1.id),
    )
    assert above.status_code == 403


async def test_office_roles_only_by_root_admin_and_never_with_unit(client, world):
    body = {"user_id": str(world.sup_b1.id), "role": "library"}
    assert (
        await client.post("/api/v1/role-assignments", json=body, headers=auth(world.admin_a1.id))
    ).status_code == 403
    with_unit = {**body, "unit_id": str(world.a1.id)}
    res = await client.post(
        "/api/v1/role-assignments", json=with_unit, headers=auth(world.root_admin.id)
    )
    assert res.json()["error"]["code"] == "unit_not_allowed"
    assert (
        await client.post("/api/v1/role-assignments", json=body, headers=auth(world.root_admin.id))
    ).status_code == 201


async def test_duplicate_role_is_409(client, world):
    body = {"user_id": str(world.meera.id), "role": "unit_head", "unit_id": str(world.a1.id)}
    res = await client.post(
        "/api/v1/role-assignments", json=body, headers=auth(world.root_admin.id)
    )
    assert (res.status_code, res.json()["error"]["code"]) == (409, "duplicate_role")


async def test_revoking_a_role_takes_effect_on_next_request(client, world, session):
    row = await session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == world.hod_a2.id, RoleAssignment.role == "unit_head"
        )
    )
    res = await client.delete(
        f"/api/v1/role-assignments/{row.id}", headers=auth(world.root_admin.id)
    )
    assert res.status_code == 204
    me = (await client.get("/api/v1/auth/me", headers=auth(world.hod_a2.id))).json()
    assert me["roles"] == []


async def test_root_admin_cannot_remove_own_admin_role(client, world, session):
    row = await session.scalar(
        select(RoleAssignment).where(RoleAssignment.user_id == world.root_admin.id)
    )
    res = await client.delete(
        f"/api/v1/role-assignments/{row.id}", headers=auth(world.root_admin.id)
    )
    assert res.json()["error"]["code"] == "cannot_revoke_own_root_admin"


async def test_admin_deactivates_user_in_subtree_only(client, world):
    ok = await client.patch(
        f"/api/v1/users/{world.scholar_a1b.id}",
        json={"is_active": False},
        headers=auth(world.admin_a1.id),
    )
    assert ok.status_code == 200 and ok.json()["is_active"] is False
    # Dean of School A can read A1 users but holds no admin role -> cannot change them.
    denied = await client.patch(
        f"/api/v1/users/{world.scholar_a1.id}",
        json={"is_active": False},
        headers=auth(world.dean_a.id),
    )
    assert denied.status_code == 403


async def test_cannot_deactivate_self(client, world):
    res = await client.patch(
        f"/api/v1/users/{world.root_admin.id}",
        json={"is_active": False},
        headers=auth(world.root_admin.id),
    )
    assert res.json()["error"]["code"] == "cannot_deactivate_self"
