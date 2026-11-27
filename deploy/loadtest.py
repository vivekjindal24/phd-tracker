"""Capacity test: how many people at once an install serves (docs/THINGS_TO_KNOW.md).

Signs in the demo university's accounts (app.seed) the way a morning rush would, then
simulated people click through the pages used most: each click makes the API calls the web
app makes for that page, then the person reads for 5-15 s. Each stage holds that many people
for a minute and reports how fast their pages came back. It changes nothing but sign-ins and
"seen" marks on notifications. It needs the demo data: a trial install, never a live one.

On an install, from its folder (/opt/anveshan on the laptop server), add `-f
deploy/compose.tunnel.yml` after compose.prod.yml if the install uses the tunnel:
    read -rs LOAD_PASSWORD            # the demo accounts' SEED_PASSWORD; not echoed
    sudo docker compose -f deploy/compose.prod.yml --env-file deploy/.env exec -T \
        -e LOAD_PASSWORD="$LOAD_PASSWORD" api python - < deploy/loadtest.py
It then runs inside the API container and goes through Caddy, like a browser.
Not behind the tunnel: also -e LOAD_URL=https://<the site's address>.
Against a local API, from services/api:
    PYTHONPATH=. LOAD_URL=http://localhost:8900 LOAD_WEB=0 python ../../deploy/loadtest.py
Stages: LOAD_STAGES=10,25,50 (people at once); LOAD_SECONDS=60 per stage.
"""

# ruff: noqa: S311  (random only paces simulated people)
import asyncio
import os
import random
import statistics
import time
from urllib.parse import urlsplit

import httpx

from app.seed import DEMO_FACULTY, DEMO_SCHOLARS, DEMO_STAFF, DOMAIN

ACCOUNTS = [f"{row[0]}@{DOMAIN}" for row in (*DEMO_STAFF, *DEMO_FACULTY, *DEMO_SCHOLARS)]
# Inside the API container behind the tunnel: Caddy over plain http, addressed by the site's
# name. Elsewhere LOAD_URL: the site's public address, or a bare API with LOAD_WEB=0.
SITE = urlsplit(os.environ.get("APP_BASE_URL", "http://localhost")).hostname
BASE = os.environ.get("LOAD_URL", "http://caddy")
HOST = {"Host": SITE} if BASE == "http://caddy" else {}
WEB = os.environ.get("LOAD_WEB", "1") == "1"  # also load the pages themselves from the web app
STAGES = [int(n) for n in os.environ.get("LOAD_STAGES", "10,25,50,100,150,200").split(",")]
SECONDS = int(os.environ.get("LOAD_SECONDS", "60"))
PASSWORD = os.environ["LOAD_PASSWORD"]
COOKIE = "anveshan_refresh"
SLOW_S = 1.0  # a page slower than this at the 95th percentile: the stage is over capacity

# (weight, page, API calls the web app makes for it)
PAGES = [
    (4, "/home", ["/dashboard", "/announcements"]),
    (2, "/queue", ["/queue"]),
    (2, "/scholars", ["/scholars"]),
    (1, "/publications", ["/publications"]),
    (1, "/notifications", ["/notifications"]),
    (1, "/todos", ["/todos"]),
    (1, "/seminars", ["/seminars"]),
    (1, "/search", ["/search?q=re"]),
]
WEIGHTS = [w for w, _, _ in PAGES]


class Person:
    def __init__(self, email: str) -> None:
        self.email = email
        self.http = httpx.AsyncClient(base_url=BASE, headers=HOST, timeout=30)
        self.token = ""
        self.refresh = ""  # sent by hand: the cookie is Secure, and Caddy is reached over http

    def _keep(self, res: httpx.Response) -> None:
        if value := res.cookies.get(COOKIE):
            self.refresh = value
        if res.is_success and "access_token" in res.text:
            self.token = res.json()["access_token"]

    async def login(self) -> httpx.Response:
        res = await self.http.post(
            "/api/v1/auth/login", json={"email": self.email, "password": PASSWORD}
        )
        self._keep(res)
        return res

    async def renew(self) -> httpx.Response:
        res = await self.http.post(
            "/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={self.refresh}"}
        )
        self._keep(res)
        return res

    async def call(self, path: str, method: str = "GET", **kw) -> httpx.Response:
        for renewed in (False, True):
            res = await self.http.request(
                method, f"/api/v1{path}", headers={"Authorization": f"Bearer {self.token}"}, **kw
            )
            if res.status_code != 401 or renewed:
                return res
            await self.renew()  # the half-hour token ran out: renew, as the web app does
        return res

    async def click(self, full_load: bool) -> list[httpx.Response]:
        _, page, calls = random.choices(PAGES, WEIGHTS)[0]
        first: list = []
        if full_load:  # a fresh tab: the page itself, a renewed session, who am I
            if WEB:
                first.append(self.http.get(page))
            first += [self.renew()]
        done = list(await asyncio.gather(*first))
        if full_load:
            done.append(await self.call("/auth/me"))
        done += await asyncio.gather(
            *(self.call(c) for c in calls),
            self.call("/notifications/opened", method="POST", json={"link": page}),
        )
        return done


class Tally:
    def __init__(self) -> None:
        self.pages: list[float] = []
        self.requests = 0
        self.failed: dict[str, int] = {}

    def add(self, seconds: float, responses: list[httpx.Response]) -> None:
        self.pages.append(seconds)
        self.requests += len(responses)
        for r in responses:  # refused by role (403/404) is an answer; any other error is not
            if r.status_code >= 400 and r.status_code not in (403, 404):
                self.fail(f"{r.status_code} {r.request.url.path}")

    def fail(self, why: str) -> None:
        self.failed[why] = self.failed.get(why, 0) + 1


def pct(values: list[float], p: int) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    return statistics.quantiles(values, n=100, method="inclusive")[p - 1]


async def browse(person: Person, until: float, tally: Tally) -> None:
    await asyncio.sleep(random.uniform(0, 10))  # people arrive spread out, not all at once
    while time.monotonic() < until:
        start = time.monotonic()
        try:
            responses = await person.click(full_load=random.random() < 0.2)
            tally.add(time.monotonic() - start, responses)
        except httpx.HTTPError as e:
            tally.fail(type(e).__name__)
        await asyncio.sleep(random.uniform(5, 15))


async def sign_in(people: list[Person]) -> None:
    """Everyone signs in within a few seconds, ten at a time (the 9 a.m. rush)."""
    times: list[float] = []
    held = 0
    gate = asyncio.Semaphore(10)

    async def one(p: Person) -> None:
        nonlocal held
        waited = False
        while True:
            async with gate:
                start = time.monotonic()
                res = await p.login()
            if res.status_code != 429:
                break
            # Past 300 a minute from one address the portal asks to wait, as for a campus
            # behind one internet address (THINGS_TO_KNOW.md, "Request limit"): wait, try again.
            waited = True
            await asyncio.sleep(int(res.headers.get("Retry-After", "5")))
        times.append(time.monotonic() - start)
        held += waited
        if not p.token:
            raise SystemExit(f"{p.email} could not sign in: {res.status_code} {res.text}")

    start = time.monotonic()
    await asyncio.gather(*(one(p) for p in people))
    took = time.monotonic() - start
    print(
        f"sign-in rush: {len(people)} sign-ins in {took:.1f} s "
        f"({len(people) / took:.1f}/s), each p50 {pct(times, 50):.2f} s p95 {pct(times, 95):.2f} s"
        + (f"; {held} asked to wait a minute (one address)" if held else "")
    )


async def main() -> None:
    print(f"target {BASE} (site {SITE}), {len(ACCOUNTS)} demo accounts, {SECONDS} s per stage")
    people = [Person(ACCOUNTS[i % len(ACCOUNTS)]) for i in range(max(STAGES))]
    await sign_in(people)
    print(
        f"{'people':>6} {'clicks':>6} {'req/s':>6} {'p50 s':>6} {'p95 s':>6} {'max s':>6}  failed"
    )
    capacity = 0
    for n in STAGES:
        tally = Tally()
        until = time.monotonic() + SECONDS
        await asyncio.gather(*(browse(p, until, tally) for p in people[:n]))
        p95 = pct(tally.pages, 95)
        failed = ", ".join(f"{k} x{v}" for k, v in tally.failed.items()) or "none"
        print(
            f"{n:>6} {len(tally.pages):>6} {tally.requests / SECONDS:>6.1f} "
            f"{pct(tally.pages, 50):>6.2f} {p95:>6.2f} {max(tally.pages, default=0):>6.2f}"
            f"  {failed}"
        )
        if tally.failed or p95 > SLOW_S:
            break
        capacity = n
    print(
        f"capacity: {capacity} people clicking at once with pages under {SLOW_S:.0f} s for 95 in"
        " 100 and nothing failed"
        if capacity
        else "capacity: below the first stage"
    )
    await asyncio.gather(*(p.http.aclose() for p in people))


if __name__ == "__main__":
    asyncio.run(main())
