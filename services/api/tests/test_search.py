"""Search: grouped, ownership-scoped, partial-match on IDs and names."""

from tests.conftest import auth_headers, login


def test_search_scoped_and_grouped(client, trio, db):
	"""Scholar B's data must not surface in scholar A's search results."""
	db.report(trio.scholar_b, state="submitted", summary="quantum annealing study")
	db.report(trio.scholar_a, state="submitted", summary="transformer survey", year=2025)
	db.commit()

	resp = client.get(
		"/api/v1/search", params={"q": "transformer"},
		headers=auth_headers(login(client, "a@x.edu")["access_token"]),
	)
	assert resp.status_code == 200
	body = resp.json()
	assert [r["summary"] for r in body["reports"]] == ["transformer survey"]

	resp = client.get(
		"/api/v1/search", params={"q": "quantum"},
		headers=auth_headers(login(client, "a@x.edu")["access_token"]),
	)
	assert resp.json()["reports"] == []  # B's report is invisible to A


def test_search_partial_roll_number_and_name(client, trio, db):
	db.commit()
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	resp = client.get("/api/v1/search", params={"q": "PHD-1"}, headers=scholar)
	assert [s["roll_number"] for s in resp.json()["scholars"]] == ["PHD-1"]

	resp = client.get("/api/v1/search", params={"q": "Asha"}, headers=scholar)
	assert [s["scholar_name"] for s in resp.json()["scholars"]] == ["Asha"]


def test_search_finds_supervisors_for_everyone(client, trio):
	# Bhavna is a scholar (not Meera's own data — directory is public within the matrix)
	token = auth_headers(login(client, "b@x.edu")["access_token"])
	resp = client.get("/api/v1/search", params={"q": "Meera"}, headers=token)
	assert [s["full_name"] for s in resp.json()["supervisors"]] == ["Dr. Meera Krishnan"]


def test_search_requires_query(client, trio):
	token = auth_headers(login(client, "admin@x.edu")["access_token"])
	resp = client.get("/api/v1/search", headers=token)
	assert resp.status_code == 422