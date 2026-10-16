"""Comment threads: target-visibility gate (no MATRIX row of their own), authoring,
author-or-admin delete, and the insert audit row."""

from tests.conftest import auth_headers, login


def _comment(client, headers, table_name, record_id, body="Looks good"):
	return client.post(
		"/api/v1/comments",
		json={"table_name": table_name, "record_id": record_id, "body": body},
		headers=headers,
	)


def test_supervisor_comments_on_own_scholars_meeting(client, trio):
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])
	meeting = client.post(
		"/api/v1/meetings",
		json={
			"scholar_id": str(trio.scholar_a),
			"supervisor_id": str(trio.supervisor_id),
			"meeting_date": "2026-10-01",
			"agenda": "Progress review",
		},
		headers=supervisor,
	).json()["id"]

	assert _comment(client, supervisor, "meetings", meeting, "Keep the pace up").status_code == 201

	listed = client.get(
		f"/api/v1/comments?table_name=meetings&record_id={meeting}", headers=supervisor
	).json()
	assert [c["body"] for c in listed] == ["Keep the pace up"]


def test_scholar_cannot_comment_on_another_scholars_record(client, trio, db):
	theirs = db.report(trio.scholar_b, state="submitted")
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])

	resp = _comment(client, scholar, "progress_reports", str(theirs), "Sneaky")
	assert resp.status_code == 403
	assert resp.json()["error"]["code"] == "permission_denied"


def test_unknown_table_is_422(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	resp = _comment(client, admin, "users", str(trio.scholar_a))
	assert resp.status_code == 422


def test_comment_insert_is_audited(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	assert _comment(client, admin, "scholars", str(trio.scholar_a)).status_code == 201

	activity = client.get("/api/v1/stats/dashboard", headers=admin).json()["recent_activity"]
	assert any(a["table_name"] == "comments" and a["action"] == "insert" for a in activity)


def test_delete_own_not_others_admin_any(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])

	by_supervisor = _comment(client, supervisor, "scholars", str(trio.scholar_a)).json()["id"]
	by_scholar = _comment(client, scholar, "scholars", str(trio.scholar_a)).json()["id"]

	# scholar may not delete the supervisor's comment…
	assert client.delete(f"/api/v1/comments/{by_supervisor}", headers=scholar).status_code == 403
	# …but their own, and admin may delete either
	assert client.delete(f"/api/v1/comments/{by_scholar}", headers=scholar).status_code == 204
	assert client.delete(f"/api/v1/comments/{by_supervisor}", headers=admin).status_code == 204

	listed = client.get(
		f"/api/v1/comments?table_name=scholars&record_id={trio.scholar_a}", headers=admin
	).json()
	assert listed == []