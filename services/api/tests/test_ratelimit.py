"""The general request limit (ratelimit.py): per signed-in user, else per client address;
over it, a 429 in the usual envelope with Retry-After, still carrying CORS headers."""

from app import ratelimit
from app.config import settings
from tests.conftest import auth
from tests.world import PASSWORD


async def test_over_the_limit_is_refused_per_key(client, world, monkeypatch):
    monkeypatch.setattr(ratelimit, "PER_ADDRESS", 3)
    monkeypatch.setattr(ratelimit, "PER_USER", 3)
    origin = next(iter(settings.cors_origins))

    for _ in range(3):
        assert (await client.get("/api/v1/privacy")).status_code == 200
    over = await client.get("/api/v1/privacy", headers={"Origin": origin})
    assert over.status_code == 429 and over.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(over.headers["Retry-After"]) <= ratelimit.WINDOW_S
    assert over.headers["access-control-allow-origin"] == origin

    # A signed-in user has a count of their own, apart from the address and from other users.
    async def me(user) -> int:
        return (await client.get("/api/v1/auth/me", headers=auth(user.id))).status_code

    assert [await me(world.scholar_a1) for _ in range(4)] == [200, 200, 200, 429]
    assert await me(world.admin_a1) == 200

    # Renewing a session is counted per session, not per address (a campus shares one).
    login = await client.post(
        "/api/v1/auth/login", json={"email": "meera@x.edu", "password": PASSWORD}
    )
    assert login.status_code == 429  # this address is over its count
    ratelimit.reset()
    assert (
        await client.post("/api/v1/auth/login", json={"email": "meera@x.edu", "password": PASSWORD})
    ).status_code == 200
    for _ in range(2):  # with the login, the address's count is used up
        assert (await client.get("/api/v1/privacy")).status_code == 200
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    assert (await client.get("/api/v1/privacy")).status_code == 429

    # Health checks are never limited.
    assert (await client.get("/api/v1/healthz")).status_code == 200
