"""Specimen signatures (PRD F17b): uploaded by the person and confirmed by a keeper (an admin over
their unit, the Research Office, the root admin), or handed in on paper and uploaded by a keeper."""

from tests.conftest import auth

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


async def put(client, by, of, content=PNG):
    return await client.put(
        f"{API}/users/{of.id}/signature",
        headers={**auth(by.id), "Content-Type": "image/png"},
        content=content,
    )


async def get(client, by, of):
    return await client.get(f"{API}/users/{of.id}/signature", headers=auth(by.id))


async def confirm(client, by, of):
    return await client.post(f"{API}/users/{of.id}/signature/confirm", headers=auth(by.id))


async def pending(client, by):
    return await client.get(f"{API}/signatures/pending", headers=auth(by.id))


async def test_own_upload_waits_until_an_admin_over_the_unit_confirms(client, world):
    assert (await get(client, world.scholar_a1, world.scholar_a1)).json() is None
    assert (await put(client, world.scholar_a1, world.scholar_a1)).status_code == 204
    mine = (await get(client, world.scholar_a1, world.scholar_a1)).json()
    assert mine["confirmed_at"] is None and mine["uploaded_by_self"] is True
    assert mine["image"].startswith("data:image/png;base64,")

    waiting = (await pending(client, world.admin_a1)).json()
    assert [w["user_id"] for w in waiting] == [str(world.scholar_a1.id)]
    assert (await confirm(client, world.admin_a1, world.scholar_a1)).status_code == 204
    assert (await get(client, world.scholar_a1, world.scholar_a1)).json()["confirmed_at"]
    assert (await pending(client, world.admin_a1)).json() == []


async def test_a_paper_signature_uploaded_by_a_keeper_is_confirmed_at_once(client, world):
    # The Research Office keeps anyone's; here a faculty member in another school.
    assert (await put(client, world.research_office, world.sup_b1, JPEG)).status_code == 204
    sig = (await get(client, world.sup_b1, world.sup_b1)).json()
    assert sig["confirmed_at"] and sig["uploaded_by_self"] is False
    assert sig["image"].startswith("data:image/jpeg;base64,")


async def test_a_new_signature_needs_confirming_again(client, world):
    await put(client, world.admin_a1, world.scholar_a1)
    await put(client, world.scholar_a1, world.scholar_a1, JPEG)
    sig = (await get(client, world.scholar_a1, world.scholar_a1)).json()
    assert sig["confirmed_at"] is None and sig["image"].startswith("data:image/jpeg")


async def test_nobody_confirms_their_own(client, world):
    await put(client, world.admin_a1, world.admin_a1)
    res = await confirm(client, world.admin_a1, world.admin_a1)
    assert res.status_code == 403 and res.json()["error"]["code"] == "own_signature"
    assert (await pending(client, world.admin_a1)).json() == []
    assert (await confirm(client, world.meera, world.admin_a1)).status_code == 204


async def test_keepers_stop_at_their_units(client, world):
    await put(client, world.sup_b1, world.sup_b1)
    assert (await confirm(client, world.admin_a1, world.sup_b1)).status_code == 403
    assert (await put(client, world.admin_a1, world.sup_b1)).status_code == 403
    assert (await get(client, world.admin_a1, world.sup_b1)).status_code == 403
    assert (await pending(client, world.admin_a1)).json() == []
    # A unit head is not a keeper, and nor is anyone else looking at a colleague's signature.
    assert (await confirm(client, world.hod_b1, world.sup_b1)).status_code == 403
    assert (await get(client, world.scholar_b1, world.sup_b1)).status_code == 403
    assert (await pending(client, world.scholar_a1)).status_code == 403


async def test_only_png_and_jpeg(client, world):
    res = await put(client, world.scholar_a1, world.scholar_a1, b"<svg onload=alert(1)>")
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_signature"


async def test_removing_leaves_nothing_to_sign_with(client, world):
    await put(client, world.admin_a1, world.scholar_a1)
    res = await client.delete(
        f"{API}/users/{world.scholar_a1.id}/signature", headers=auth(world.scholar_a1.id)
    )
    assert res.status_code == 204
    assert (await get(client, world.scholar_a1, world.scholar_a1)).json() is None
