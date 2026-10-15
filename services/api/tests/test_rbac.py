"""RBAC: the v1-gap regression (ownership), list scoping, and negative permission cases.

SECURITY.md §2 restated: scholar sees only own records; supervisor only own
scholars'; admin everything. Denials come back as the 403 envelope, never data.
"""

from tests.conftest import auth_headers, login


def test_scholar_cannot_read_another_scholars_records(client, trio, db):
	"""The regression test for the v1 Frappe gap — this must never pass by accident."""
	own = db.report(trio.scholar_a, state="submitted")
	theirs = db.report(trio.scholar_b, state="submitted")
	db.commit()
	token = login(client, "a@x.edu")["access_token"]

	resp = client.get(f"/api/v1/reports/{own}", headers=auth_headers(token))
	assert resp.status_code == 200

	resp = client.get(f"/api/v1/reports/{theirs}", headers=auth_headers(token))
	assert resp.status_code == 403
	assert resp.json()["error"]["code"] == "permission_denied"


def test_list_scoping_by_role(client, trio, db):
	db.report(trio.scholar_a, state="submitted")
	db.report(trio.scholar_b, state="submitted")
	db.commit()

	scholar_items = client.get(
		"/api/v1/reports", headers=auth_headers(login(client, "a@x.edu")["access_token"])
	).json()
	assert [i["scholar_id"] for i in scholar_items["items"]] == [str(trio.scholar_a)]

	supervisor_items = client.get(
		"/api/v1/reports", headers=auth_headers(login(client, "meera@x.edu")["access_token"])
	).json()
	assert supervisor_items["total"] == 2  # both scholars are Meera's

	admin_items = client.get(
		"/api/v1/reports", headers=auth_headers(login(client, "admin@x.edu")["access_token"])
	).json()
	assert admin_items["total"] == 2


def test_scholar_sees_only_own_profile(client, trio):
	token = login(client, "a@x.edu")["access_token"]
	items = client.get("/api/v1/scholars", headers=auth_headers(token)).json()["items"]
	assert len(items) == 1
	assert items[0]["roll_number"] == "PHD-1"

	resp = client.get(f"/api/v1/scholars/{trio.scholar_b}", headers=auth_headers(token))
	assert resp.status_code == 403


def test_directory_readable_by_all_roles(client, trio):
	for email in ("a@x.edu", "meera@x.edu", "admin@x.edu"):
		token = login(client, email)["access_token"]
		resp = client.get("/api/v1/supervisors", headers=auth_headers(token))
		assert resp.status_code == 200
		assert resp.json()["total"] == 1


def test_negative_permission_matrix(client, trio):
	# scholar may not create scholars or milestones, or delete anything
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	assert client.post(
		"/api/v1/scholars",
		json={"scholar_name": "X", "roll_number": "NEW", "department": "CS", "admission_date": "2024-07-01"},
		headers=scholar,
	).status_code == 403
	assert client.post(
		"/api/v1/milestones",
		json={"scholar_id": str(trio.scholar_a), "milestone_type": "Viva Voce"},
		headers=scholar,
	).status_code == 403
	assert client.delete(
		f"/api/v1/scholars/{trio.scholar_a}", headers=scholar
	).status_code == 403

	# supervisor may not create scholars or supervisors
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])
	assert client.post(
		"/api/v1/scholars",
		json={"scholar_name": "X", "roll_number": "NEW", "department": "CS", "admission_date": "2024-07-01"},
		headers=supervisor,
	).status_code == 403
	assert client.post(
		"/api/v1/supervisors",
		json={"full_name": "Y", "email": "y@x.edu", "department": "CS", "designation": "Professor"},
		headers=supervisor,
	).status_code == 403


def test_admin_soft_delete_hides_rows(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	assert client.delete(f"/api/v1/scholars/{trio.scholar_a}", headers=admin).status_code == 204
	resp = client.get(f"/api/v1/scholars/{trio.scholar_a}", headers=admin)
	assert resp.status_code == 403
	assert client.get("/api/v1/scholars", headers=admin).json()["total"] == 1


def test_internal_export_endpoints_are_admin_only(client, trio):
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	resp = client.get("/api/v1/internal/milestones", headers=scholar)
	assert resp.status_code == 403