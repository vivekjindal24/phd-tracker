"""List sorting/filtering: whitelisted sort, equality filters, stable default order —
and none of it can widen the RBAC scope (filters compose after live_and_scoped)."""

from tests.conftest import auth_headers, login


def test_sort_asc_and_desc(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])

	asc = client.get("/api/v1/scholars?sort=roll_number", headers=admin).json()["items"]
	assert [s["roll_number"] for s in asc] == ["PHD-1", "PHD-2"]

	desc = client.get("/api/v1/scholars?sort=-roll_number", headers=admin).json()["items"]
	assert [s["roll_number"] for s in desc] == ["PHD-2", "PHD-1"]


def test_unknown_sort_column_is_422(client, trio):
	"""Non-whitelisted column — even a real one like github_url — never reaches order_by."""
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	resp = client.get("/api/v1/scholars?sort=github_url", headers=admin)
	assert resp.status_code == 422
	assert resp.json()["error"]["code"] == "bad_sort"


def test_default_order_is_newest_first(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	body = {"scholar_name": "Chetan", "roll_number": "PHD-3", "department": "CS",
		"admission_date": "2025-01-01"}
	assert client.post("/api/v1/scholars", json=body, headers=admin).status_code == 201

	items = client.get("/api/v1/scholars", headers=admin).json()["items"]
	assert items[0]["roll_number"] == "PHD-3"  # newest row leads an unsorted page


def test_department_and_stage_filter(client, trio, db):
	db.scholar("PHD-9", "Deepa", supervisor_id=trio.supervisor_id, department="Physics")
	db.commit()
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])

	cs = client.get("/api/v1/scholars?department=CS", headers=admin).json()
	assert cs["total"] == 2
	physics = client.get("/api/v1/scholars?department=Physics", headers=admin).json()
	assert physics["total"] == 1

	admin_patch = {"stage": "Coursework"}
	resp = client.patch(f"/api/v1/scholars/{trio.scholar_a}", json=admin_patch, headers=admin)
	assert resp.status_code == 200
	coursework = client.get("/api/v1/scholars?stage=Coursework", headers=admin).json()
	assert coursework["total"] == 1
	assert coursework["items"][0]["roll_number"] == "PHD-1"


def test_filters_compose_with_rbac_scope(client, trio, db):
	"""Sorting and filtering are applied after the scope — scholar A never sees B."""
	db.report(trio.scholar_a, state="submitted")
	db.report(trio.scholar_b, state="submitted")
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])

	resp = client.get("/api/v1/reports?state=submitted&sort=-report_year", headers=scholar).json()
	assert resp["total"] == 1
	assert resp["items"][0]["scholar_id"] == str(trio.scholar_a)


def test_reports_state_and_year_filters(client, trio, db):
	own = db.report(trio.scholar_a, state="submitted", year=2025)
	db.report(trio.scholar_a, state="draft", year=2026)
	db.commit()
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])

	submitted = client.get("/api/v1/reports?state=submitted", headers=supervisor).json()
	assert submitted["total"] == 1
	assert submitted["items"][0]["id"] == str(own)

	y2025 = client.get("/api/v1/reports?report_year=2025", headers=supervisor).json()
	assert y2025["total"] == 1
	year_and_state = client.get(
		"/api/v1/reports?report_year=2025&state=draft", headers=supervisor
	).json()
	assert year_and_state["total"] == 0