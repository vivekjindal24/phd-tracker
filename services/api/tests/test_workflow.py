"""The APR workflow — every legal transition, one illegal per role, the duplicate-APR
409, the UGC cap 409, and approved-report immutability."""

import uuid

from tests.conftest import auth_headers, login


def _post_action(client, token, report_id, action):
	return client.post(
		f"/api/v1/reports/{report_id}/{action}", headers=auth_headers(token)
	)


def test_full_lifecycle_submit_approve(client, trio, db):
	report = db.report(trio.scholar_a, state="draft")
	db.commit()
	scholar = login(client, "a@x.edu")["access_token"]
	supervisor = login(client, "meera@x.edu")["access_token"]

	resp = _post_action(client, scholar, report, "submit")
	assert resp.status_code == 200 and resp.json()["state"] == "submitted"

	resp = _post_action(client, supervisor, report, "approve")
	assert resp.status_code == 200
	body = resp.json()
	assert body["state"] == "approved"
	assert body["approved_on"] is not None  # the compliance stamp


def test_send_back_and_resubmit_cycle(client, trio, db):
	report = db.report(trio.scholar_a, state="submitted")
	db.commit()
	scholar = login(client, "a@x.edu")["access_token"]
	supervisor = login(client, "meera@x.edu")["access_token"]

	resp = _post_action(client, supervisor, report, "send_back")
	assert resp.status_code == 200 and resp.json()["state"] == "rejected"

	resp = _post_action(client, scholar, report, "resubmit")
	assert resp.status_code == 200 and resp.json()["state"] == "draft"

	resp = _post_action(client, scholar, report, "submit")
	assert resp.status_code == 200 and resp.json()["state"] == "submitted"


def test_wrong_role_cannot_submit(client, trio, db):
	"""Plan's named illegal case: supervisor tries submit → 422."""
	report = db.report(trio.scholar_a, state="draft")
	db.commit()
	supervisor = login(client, "meera@x.edu")["access_token"]
	resp = _post_action(client, supervisor, report, "submit")
	assert resp.status_code == 422
	assert resp.json()["error"]["code"] == "workflow_violation"


def test_supervisor_cannot_approve_own_scholars_draft(client, trio, db):
	report = db.report(trio.scholar_a, state="draft")
	db.commit()
	supervisor = login(client, "meera@x.edu")["access_token"]
	resp = _post_action(client, supervisor, report, "approve")
	assert resp.status_code == 422


def test_supervisor_cannot_act_on_other_scholars_reports(client, db, trio):
	"""Row-level guard: Meera's token hits a report of a scholar she doesn't supervise."""
	db.user("other@x.edu", "scholar", "Cara")
	sup2 = db.supervisor("raj@x.edu", "Dr. Rajesh Nair")
	other_scholar = db.scholar("PHD-3", "Cara", supervisor_id=sup2)
	report = db.report(other_scholar, state="submitted")
	db.commit()

	resp = _post_action(client, login(client, "meera@x.edu")["access_token"], report, "approve")
	assert resp.status_code == 403  # invisible row, not a 422 role error


def test_edit_rules_follow_state(client, trio, db):
	draft = db.report(trio.scholar_a, state="draft")
	submitted = db.report(trio.scholar_a, state="submitted", year=2025, period="July-December")
	approved = db.report(trio.scholar_a, state="approved", year=2024)
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])

	# scholar edits own draft, not own submitted
	assert client.patch(
		f"/api/v1/reports/{draft}", json={"summary": "Revised"}, headers=scholar
	).status_code == 200
	assert client.patch(
		f"/api/v1/reports/{submitted}", json={"summary": "Revised"}, headers=scholar
	).status_code == 422

	# supervisor comments on submitted, can't edit a draft
	assert client.patch(
		f"/api/v1/reports/{submitted}", json={"supervisor_comment": "Fine"}, headers=supervisor
	).status_code == 200
	assert client.patch(
		f"/api/v1/reports/{draft}", json={"supervisor_comment": "No"}, headers=supervisor
	).status_code == 422

	# approved is immutable for everyone
	assert client.patch(
		f"/api/v1/reports/{approved}", json={"summary": "Tamper"}, headers=supervisor
	).status_code == 422
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	assert client.patch(
		f"/api/v1/reports/{approved}", json={"summary": "Tamper"}, headers=admin
	).status_code == 422


def test_duplicate_apr_is_409(client, trio, db):
	db.report(trio.scholar_a, state="approved", year=2026, period="January-June")
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	resp = client.post(
		"/api/v1/reports",
		json={"scholar_id": str(trio.scholar_a),
			"report_year": 2026, "period": "January-June", "summary": "S"},
		headers=scholar,
	)
	assert resp.status_code == 409
	assert resp.json()["error"]["code"] == "duplicate_apr"

	# the other period is fine
	resp = client.post(
		"/api/v1/reports",
		json={"scholar_id": str(trio.scholar_a),
			"report_year": 2026, "period": "July-December", "summary": "S"},
		headers=scholar,
	)
	assert resp.status_code == 201


def test_ugc_cap_is_409(client, trio, db):
	"""Assistant Professor caps at 4: the 5th assignment is refused."""
	assistant = db.supervisor(
		"prof@x.edu", "Dr. New Prof", designation="Assistant Professor", user_id=None
	)
	db.commit()
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	for i in range(4):
		resp = client.post(
			"/api/v1/scholars",
			json={
				"scholar_name": f"S{i}", "roll_number": f"CAP-{i}", "department": "CS",
				"admission_date": "2024-07-01", "supervisor_id": str(assistant),
			},
			headers=admin,
		)
		assert resp.status_code == 201, resp.text
	resp = client.post(
		"/api/v1/scholars",
		json={
			"scholar_name": "S5", "roll_number": "CAP-5", "department": "CS",
			"admission_date": "2024-07-01", "supervisor_id": str(assistant),
		},
		headers=admin,
	)
	assert resp.status_code == 409
	assert resp.json()["error"]["code"] == "supervisor_cap_exceeded"


def test_unknown_report_id_is_403_not_404(client, trio):
	token = auth_headers(login(client, "a@x.edu")["access_token"])
	resp = client.get(f"/api/v1/reports/{uuid.uuid4()}", headers=token)
	assert resp.status_code == 403  # existence is not leaked