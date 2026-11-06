"""Per-install branding: address and logo set by the root admin, read in public (the login page
shows them before anyone signs in) and printed on every PDF."""

import base64

import pytest

from tests.conftest import auth

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


async def put_logo(client, user, content, content_type="image/png"):
    return await client.put(
        f"{API}/settings/logo",
        headers={**auth(user.id), "Content-Type": content_type},
        content=content,
    )


async def test_public_branding_before_anything_is_set(client, world):
    res = await client.get(f"{API}/branding")  # no login
    assert res.status_code == 200
    body = res.json()
    assert body["university"] == world.root.name
    assert body["address"] == "" and body["has_logo"] is False


async def test_root_admin_sets_address_and_logo(client, world):
    res = await client.patch(
        f"{API}/settings",
        headers=auth(world.root_admin.id),
        json={"university_address": "Sector 1, Gandhinagar"},
    )
    assert res.status_code == 200
    assert (await put_logo(client, world.root_admin, PNG)).status_code == 204

    body = (await client.get(f"{API}/branding")).json()
    assert body["address"] == "Sector 1, Gandhinagar" and body["has_logo"] is True
    logo = await client.get(f"{API}/branding/logo")  # no login
    assert logo.status_code == 200 and logo.content == PNG
    assert logo.headers["content-type"] == "image/png"
    assert logo.headers["x-content-type-options"] == "nosniff"


async def test_type_comes_from_the_bytes_not_the_header(client, world):
    await put_logo(client, world.root_admin, JPEG, "image/png")
    logo = await client.get(f"{API}/branding/logo")
    assert logo.headers["content-type"] == "image/jpeg"


@pytest.mark.parametrize(
    "content",
    [b"<svg onload=alert(1)>", b"GIF89a" + b"\x00" * 64, b""],
)
async def test_only_png_and_jpeg_are_accepted(client, world, content):
    res = await put_logo(client, world.root_admin, content, "image/svg+xml")
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_logo"


async def test_oversized_logo_is_refused(client, world):
    res = await put_logo(client, world.root_admin, PNG + b"\x00" * 500_001)
    assert res.status_code == 413 and res.json()["error"]["code"] == "logo_too_large"


@pytest.mark.parametrize("who", ["admin_a1", "research_office", "scholar_a1"])
async def test_only_the_root_admin_changes_branding(client, world, who):
    assert (await put_logo(client, getattr(world, who), PNG)).status_code == 403
    res = await client.delete(f"{API}/settings/logo", headers=auth(getattr(world, who).id))
    assert res.status_code == 403


async def test_removing_the_logo(client, world):
    await put_logo(client, world.root_admin, PNG)
    res = await client.delete(f"{API}/settings/logo", headers=auth(world.root_admin.id))
    assert res.status_code == 204
    assert (await client.get(f"{API}/branding")).json()["has_logo"] is False
    assert (await client.get(f"{API}/branding/logo")).status_code == 404


async def test_every_export_view_carries_the_branding(client, world):
    await put_logo(client, world.root_admin, PNG)
    res = await client.get(f"{API}/internal/register-view", headers=auth(world.research_office.id))
    assert res.status_code == 200
    assert res.json()["university"] == world.root.name
    assert base64.b64decode(res.json()["logo"]) == PNG
