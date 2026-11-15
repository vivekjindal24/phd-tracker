"""Fellowship monthly claims (PRD M6): a scholar claims one month of their own active
fellowship, once, and the chain certifies it — including who never sees or raises one."""

from datetime import UTC, datetime, timedelta

from tests.conftest import auth
from tests.test_grants import API, fellowship, grants_on  # noqa: F401  (fixture)

TODAY = datetime.now(UTC).date()


def ym(back: int = 0) -> str:
    """The month `back` months before this one, as YYYY-MM."""
    year, month = divmod(TODAY.year * 12 + TODAY.month - 1 - back, 12)
    return f"{year:04d}-{month + 1:02d}"


async def running(client, world, **over) -> str:
    """A fellowship of scholar_a1 that began about a year ago and runs on."""
    body = {"start_date": f"{ym(12)}-01", "end_date": str(TODAY + timedelta(days=200))} | over
    res = await fellowship(client, world, **body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def claim(client, user, fid, month=None, **over):
    body = {"fellowship_id": fid, "month": month or ym(1)} | over
    return await client.post(f"{API}/fellowship-claims", headers=auth(user.id), json=body)


async def act(client, user, cid, action, body=None):
    return await client.post(
        f"{API}/items/fellowship_claim/{cid}/{action}", headers=auth(user.id), json=body or {}
    )


async def listed(client, user) -> list[str]:
    res = await client.get(f"{API}/fellowship-claims", headers=auth(user.id))
    assert res.status_code == 200, res.text
    return [c["id"] for c in res.json()]


async def test_a_claim_runs_supervisor_department_research_office(client, world, grants_on):  # noqa: F811
    fid = await running(client, world)
    made = await claim(client, world.scholar_a1, fid, leave_days=2, note="Two days casual leave")
    assert made.status_code == 201, made.text
    item = made.json()
    assert (item["label"], item["state"]) == ("Fellowship claim", "draft")
    assert item["content"]["amount"] == 40000 and item["content"]["leave_days"] == 2
    assert item["content"]["month"] == f"{ym(1)}-01"
    cid = item["id"]
    assert (await act(client, world.scholar_a1, cid, "submit")).status_code == 200
    early = await act(client, world.research_office, cid, "approve")  # the guide's step first
    assert early.json()["error"]["code"] == "workflow_violation"
    for user in (world.meera, world.admin_a1, world.research_office):
        res = await act(client, user, cid, "approve")
        assert res.status_code == 200, res.text
    assert res.json()["state"] == "approved"
    row = (await client.get(f"{API}/fellowship-claims", headers=auth(world.scholar_a1.id))).json()[
        0
    ]
    assert (row["state"], row["scheme"], row["amount"]) == ("approved", "ugc_jrf", 40000)


async def test_one_claim_a_month_inside_a_running_fellowship(client, world, grants_on):  # noqa: F811
    fid = await running(client, world)
    assert (await claim(client, world.scholar_a1, fid)).status_code == 201
    again = await claim(client, world.scholar_a1, fid)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "duplicate_claim")
    assert (await claim(client, world.scholar_a1, fid, ym(0))).status_code == 201  # this month
    for month in (ym(13), ym(-1)):  # before it began; not begun yet
        res = await claim(client, world.scholar_a1, fid, month)
        assert (res.status_code, res.json()["error"]["code"]) == (422, "invalid_month"), month
    assert (await claim(client, world.scholar_a1, fid, f"{ym(2)}-15")).status_code == 422
    assert (await claim(client, world.scholar_a1, fid, ym(2), leave_days=32)).status_code == 422
    ended = await client.patch(
        f"{API}/fellowships/{fid}", headers=auth(world.admin_a1.id), json={"status": "terminated"}
    )
    assert ended.status_code == 200, ended.text
    res = await claim(client, world.scholar_a1, fid, ym(2))
    assert (res.status_code, res.json()["error"]["code"]) == (422, "fellowship_not_active")


async def test_only_the_fellow_claims_and_only_their_chain_reads(client, world, grants_on):  # noqa: F811
    fid = await running(client, world)
    # Another scholar, the guide and the office cannot raise a claim on it.
    assert (await claim(client, world.scholar_a2, fid)).status_code == 403
    for user in (world.meera, world.admin_a1, world.research_office):
        assert (await claim(client, user, fid)).status_code == 403, user.email
    cid = (await claim(client, world.scholar_a1, fid)).json()["id"]
    item = f"{API}/items/fellowship_claim/{cid}"
    for user in (world.scholar_a1, world.meera, world.dean_a, world.research_office):
        assert cid in await listed(client, user), user.email
        assert (await client.get(item, headers=auth(user.id))).status_code == 200, user.email
    for user in (world.scholar_a2, world.sup_b1, world.hod_b1, world.hod_a2):
        assert await listed(client, user) == [], user.email
        assert (await client.get(item, headers=auth(user.id))).status_code == 403, user.email
    for user in (world.exam_office, world.library):  # not their record at all
        res = await client.get(f"{API}/fellowship-claims", headers=auth(user.id))
        assert res.status_code == 403, user.email


async def test_sent_back_claim_is_corrected_and_carries_the_current_amount(
    client,
    world,
    grants_on,  # noqa: F811
):
    fid = await running(client, world)
    cid = (await claim(client, world.scholar_a1, fid)).json()["id"]
    edit = f"{API}/fellowship-claims/{cid}"
    mine = auth(world.scholar_a1.id)
    assert (await act(client, world.scholar_a1, cid, "submit")).status_code == 200
    locked = await client.patch(edit, headers=mine, json={"leave_days": 3})
    assert locked.json()["error"]["code"] == "workflow_violation"
    back = await act(client, world.meera, cid, "send-back", {"comment": "You were away 3 days."})
    assert back.status_code == 200, back.text
    theirs = await client.patch(edit, headers=auth(world.meera.id), json={"leave_days": 3})
    assert theirs.status_code == 403  # the guide sends back; the scholar corrects
    fixed = await client.patch(edit, headers=mine, json={"leave_days": 3})
    assert fixed.status_code == 200 and fixed.json()["content"]["leave_days"] == 3
    # The SRF upgrade lands before the resubmit: the claim takes the new amount.
    raised = await client.patch(
        f"{API}/fellowships/{fid}", headers=auth(world.admin_a1.id), json={"amount_monthly": 42000}
    )
    assert raised.status_code == 200, raised.text
    again = await act(client, world.scholar_a1, cid, "resubmit")
    assert again.status_code == 200, again.text
    assert again.json()["content"]["amount"] == 45000


async def test_claims_go_with_the_fellowships_module(client, world):
    res = await client.get(f"{API}/fellowship-claims", headers=auth(world.research_office.id))
    assert (res.status_code, res.json()["error"]["code"]) == (404, "module_disabled")
