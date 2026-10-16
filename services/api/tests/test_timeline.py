"""Per-scholar timeline: merged, newest-first, all five event kinds; visibility is
the scholar row's get_or_403."""

from tests.conftest import auth_headers, login


def _seed_rich_history(client, trio):
	"""Meeting, report, workflow transition, milestone, comment — for scholar A."""
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])
	client.post(
		"/api/v1/meetings",
		json={
			"scholar_id": str(trio.scholar_a),
			"supervisor_id": str(trio.supervisor_id),
			"meeting_date": "2026-09-01",
			"agenda": "Progress review",
		},
		headers=supervisor,
	)
	client.post(
		"/api/v1/milestones",
		json={"scholar_id": str(trio.scholar_a), "milestone_type": "Coursework Completion"},
		headers=supervisor,
	)
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	report = client.post(
		"/api/v1/reports",
		json={
			"scholar_id": str(trio.scholar_a),
			"report_year": 2026,
			"period": "January-June",
			"summary": "Coursework done",
		},
		headers=scholar,
	).json()
	client.post(f"/api/v1/reports/{report['id']}/submit", headers=scholar)
	client.post(
		"/api/v1/comments",
		json={"table_name": "progress_reports", "record_id": report["id"], "body": "On track"},
		headers=supervisor,
	)
	return report["id"]


def test_timeline_merges_and_sorts_all_kinds(client, trio):
	_seed_rich_history(client, trio)
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])

	resp = client.get(f"/api/v1/scholars/{trio.scholar_a}/timeline", headers=supervisor)
	assert resp.status_code == 200
	events = resp.json()["events"]

	kinds = {e["kind"] for e in events}
	assert kinds == {"meeting", "report", "transition", "milestone", "comment"}
	assert events == sorted(events, key=lambda e: e["at"], reverse=True)  # newest first

	transition = next(e for e in events if e["kind"] == "transition")
	assert transition["data"]["to_state"] == "submitted"


def test_timeline_is_scoped_to_the_scholar(client, trio, db):
	_seed_rich_history(client, trio)  # history belongs to A
	theirs = db.report(trio.scholar_b, state="submitted")
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	supervisor = auth_headers(login(client, "meera@x.edu")["access_token"])

	# scholar A: own timeline fine, B's is 403
	assert client.get(f"/api/v1/scholars/{trio.scholar_a}/timeline", headers=scholar).status_code == 200
	assert client.get(f"/api/v1/scholars/{trio.scholar_b}/timeline", headers=scholar).status_code == 403

	# Meera sees A's events, but nothing pinned to B's report may leak into A's feed
	events = client.get(f"/api/v1/scholars/{trio.scholar_a}/timeline", headers=supervisor).json()["events"]
	for e in events:
		assert str(theirs) not in str(e["data"])