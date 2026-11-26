"""Scholar photos (PRD F6, photos.py): seen by whoever may open the profile; put there or taken
away by the scholar or an admin over their unit."""

from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import auth
from tests.test_signatures import JPEG, PNG

API = "/api/v1/scholars"


async def get(client, by, scholar):
    return await client.get(f"{API}/{scholar.id}/photo", headers=auth(by.id))


async def put(client, by, scholar, content=PNG):
    return await client.put(
        f"{API}/{scholar.id}/photo",
        headers={**auth(by.id), "Content-Type": "image/png"},
        content=content,
    )


async def test_scholar_uploads_and_supervisor_sees_it(client, session, world):
    assert (await get(client, world.scholar_a2, world.s_a2)).json() == {
        "image": None,
        "can_change": True,
    }
    assert (await put(client, world.scholar_a2, world.s_a2)).status_code == 204

    seen = (await get(client, world.sup_a2, world.s_a2)).json()
    assert seen["image"].startswith("data:image/png;base64,") and not seen["can_change"]
    assert (await put(client, world.sup_a2, world.s_a2)).status_code == 403
    gone = await client.delete(f"{API}/{world.s_a2.id}/photo", headers=auth(world.sup_a2.id))
    assert gone.status_code == 403

    logged = await session.scalars(select(AuditLog).where(AuditLog.table_name == "scholar_photos"))
    assert [a.action for a in logged] == ["insert"]


async def test_admin_over_the_unit_replaces_and_removes(client, world):
    assert (await put(client, world.scholar_a1, world.s_a1)).status_code == 204
    assert (await get(client, world.admin_a1, world.s_a1)).json()["can_change"]
    assert (await put(client, world.admin_a1, world.s_a1, JPEG)).status_code == 204
    image = (await get(client, world.scholar_a1, world.s_a1)).json()["image"]
    assert image.startswith("data:image/jpeg;base64,")

    removed = await client.delete(f"{API}/{world.s_a1.id}/photo", headers=auth(world.admin_a1.id))
    assert removed.status_code == 204
    assert (await get(client, world.scholar_a1, world.s_a1)).json()["image"] is None


async def test_others_cannot_see_or_change(client, world):
    await put(client, world.scholar_a1, world.s_a1)
    assert (await get(client, world.scholar_b1, world.s_a1)).status_code == 403
    assert (await put(client, world.scholar_b1, world.s_a1)).status_code == 403
    assert (await put(client, world.hod_b1, world.s_a1)).status_code == 403


async def test_only_png_or_jpeg(client, world):
    res = await put(client, world.scholar_a1, world.s_a1, b"<svg onload='x'></svg>")
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_photo"
