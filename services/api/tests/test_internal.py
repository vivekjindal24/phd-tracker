"""Export read models obey the same scope as the pages (SECURITY.md §6)."""

from tests.conftest import auth

SUMMARY = "This period: survey finished, first baselines run, chapter two drafted."


async def test_report_export_view_is_scoped(client, world):
    r = (
        await client.post(
            "/api/v1/reports",
            headers=auth(world.scholar_a1.id),
            json={"report_year": 2026, "period": "July-December", "summary": SUMMARY},
        )
    ).json()
    url = f"/api/v1/internal/reports/{r['id']}/export-view"
    view = (await client.get(url, headers=auth(world.meera.id))).json()
    assert (view["scholar"], view["roll_number"], view["supervisor"]) == (
        "Scholar A1",
        "PHD-A1-001",
        "Meera",
    )
    assert view["university"] == "Test University" and view["state"] == "draft"
    for outsider in (world.scholar_b1, world.hod_b1, world.library):
        assert (await client.get(url, headers=auth(outsider.id))).status_code == 403


async def test_register_view_is_scoped(client, world):
    for s in (world.s_a1, world.s_b1):
        await client.post(
            "/api/v1/milestones",
            headers=auth(world.research_office.id),
            json={
                "scholar_id": str(s.id),
                "milestone_type": "viva",
                "status": "Approved",
                "approval_body": "RDC",
                "resolution_number": f"R-{s.roll_number}",
            },
        )
    office = (
        await client.get("/api/v1/internal/register-view", headers=auth(world.research_office.id))
    ).json()
    assert len(office["rows"]) == 2
    hod = (await client.get("/api/v1/internal/register-view", headers=auth(world.hod_b1.id))).json()
    assert [r["scholar"] for r in hod["rows"]] == ["Scholar B1"]
    lib = await client.get("/api/v1/internal/register-view", headers=auth(world.library.id))
    assert lib.status_code == 403
