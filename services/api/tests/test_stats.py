"""Dashboard aggregates: role-scoped counts, future-only upcoming meetings,
admin-only recent activity."""

from tests.conftest import auth_headers, login


def test_admin_dashboard_counts(client, trio, db):
	db.report(trio.scholar_a, state="submitted", period="January-June")
	db.report(trio.scholar_a, state="draft", period="July-December")
	db.commit()
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	assert client.patch(
		f"/api/v1/scholars/{trio.scholar_a}", json={"stage": "Coursework"}, headers=admin
	).status_code == 200  # an audited mutation, so recent_activity has something to show

	dash = client.get("/api/v1/stats/dashboard", headers=admin).json()
	assert dash["scholars"] == 2
	assert dash["supervisors"] == 1
	assert dash["reports_by_state"] == {"submitted": 1, "draft": 1}
	assert dash["scholars_by_stage"] == {"Coursework": 1, "Registered": 1}
	assert any(a["action"] == "update" for a in dash["recent_activity"])


def test_scholar_dashboard_is_their_slice(client, trio, db):
	db.report(trio.scholar_a, state="submitted")
	db.report(trio.scholar_b, state="submitted")
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])

	dash = client.get("/api/v1/stats/dashboard", headers=scholar).json()
	assert dash["scholars"] == 1  # own row only
	assert dash["supervisors"] == 1  # directory is readable by all roles
	assert dash["reports_by_state"] == {"submitted": 1}  # B's report never appears
	assert dash["scholars_by_stage"] == {"Registered": 1}
	assert dash["recent_activity"] == []  # admin-only


def test_upcoming_meetings_future_only_and_scoped(client, trio, db):
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])
	for scholar_id, date in ((trio.scholar_a, "2026-01-01"), (trio.scholar_b, "2030-01-01")):
		client.post(
			"/api/v1/meetings",
			json={
				"scholar_id": str(scholar_id),
				"supervisor_id": str(trio.supervisor_id),
				"meeting_date": date,
			},
			headers=supervisor,
		)

	sup_dash = client.get("/api/v1/stats/dashboard", headers=supervisor).json()
	assert [m["meeting_date"] for m in sup_dash["upcoming_meetings"]] == ["2030-01-01"]
	assert sup_dash["upcoming_meetings"][0]["scholar_name"] == "Bhavna"

	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	a_dash = client.get("/api/v1/stats/dashboard", headers=scholar).json()
	assert a_dash["upcoming_meetings"] == []  # A's 2026-01-01 is already past

	scholar_b = auth_headers(login(client, "b@x.edu")["access_token"])
	b_dash = client.get("/api/v1/stats/dashboard", headers=scholar_b).json()
	assert len(b_dash["upcoming_meetings"]) == 1
	assert b_dash["upcoming_meetings"][0]["scholar_name"] == "Bhavna"  # not A's