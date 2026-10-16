"""Attachments: upload/download roundtrip, the 2MB cap, and the target-visibility
gate (a scholar can never reach another scholar's file)."""

from tests.conftest import auth_headers, login

TWO_MB = 2 * 1024 * 1024


def _upload(client, headers, table_name, record_id, content=b"hello", name="notes.txt"):
	return client.post(
		"/api/v1/attachments",
		files={"file": (name, content, "text/plain")},
		data={"table_name": table_name, "record_id": record_id},
		headers=headers,
	)


def test_upload_download_roundtrip(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	resp = _upload(client, admin, "scholars", str(trio.scholar_a))
	assert resp.status_code == 201
	att = resp.json()
	assert att["size_bytes"] == 5
	assert "content" not in att  # metadata only, never the bytes

	download = client.get(f"/api/v1/attachments/{att['id']}/download", headers=admin)
	assert download.status_code == 200
	assert download.content == b"hello"
	assert download.headers["content-type"].startswith("text/plain")
	assert 'filename="notes.txt"' in download.headers["content-disposition"]


def test_over_2mb_rejected_and_leaves_no_row(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	resp = _upload(client, admin, "scholars", str(trio.scholar_a), b"x" * (TWO_MB + 1))
	assert resp.status_code == 413
	assert resp.json()["error"]["code"] == "too_large"

	listed = client.get(
		f"/api/v1/attachments?table_name=scholars&record_id={trio.scholar_a}", headers=admin
	).json()
	assert listed == []


def test_scholar_cannot_touch_another_scholars_attachments(client, trio, db):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])
	theirs = db.report(trio.scholar_b, state="submitted")
	db.commit()
	on_b = _upload(client, admin, "progress_reports", str(theirs)).json()["id"]

	# attach to another's record: 403 before any row is written
	assert _upload(client, scholar, "progress_reports", str(theirs)).status_code == 403
	# download another's file: 403 — the target's get_or_403 is the gate
	assert client.get(f"/api/v1/attachments/{on_b}/download", headers=scholar).status_code == 403
	# list another record's attachments: 403 too
	assert client.get(
		f"/api/v1/attachments?table_name=progress_reports&record_id={theirs}", headers=scholar
	).status_code == 403


def test_delete_own_other_admin_and_soft_deleted_is_gone(client, trio):
	admin = auth_headers(login(client, "admin@x.edu")["access_token"])
	scholar = auth_headers(login(client, "a@x.edu")["access_token"])

	own = _upload(client, scholar, "scholars", str(trio.scholar_a)).json()["id"]
	by_admin = _upload(client, admin, "scholars", str(trio.scholar_a)).json()["id"]

	# scholar cannot delete the admin's upload; admin can delete the scholar's
	assert client.delete(f"/api/v1/attachments/{by_admin}", headers=scholar).status_code == 403
	assert client.delete(f"/api/v1/attachments/{own}", headers=scholar).status_code == 204
	assert client.get(f"/api/v1/attachments/{own}/download", headers=scholar).status_code == 404
	assert client.delete(f"/api/v1/attachments/{by_admin}", headers=admin).status_code == 204