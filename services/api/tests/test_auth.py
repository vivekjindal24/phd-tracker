"""Auth: login, token refresh rotation, logout, admin-gated register, /me links."""

from tests.conftest import auth_headers, login


def test_login_success_and_bad_password(client, trio):
	tokens = login(client, "a@x.edu")
	assert tokens["user"]["role"] == "scholar"

	resp = client.post("/api/v1/auth/login", json={"email": "a@x.edu", "password": "wrong"})
	assert resp.status_code == 401
	assert resp.json()["error"]["code"] == "invalid_credentials"

	# unknown email gets the same message — no user enumeration
	resp = client.post("/api/v1/auth/login", json={"email": "ghost@x.edu", "password": "x"})
	assert resp.status_code == 401
	assert resp.json()["error"]["code"] == "invalid_credentials"


def test_me_returns_entity_links(client, trio):
	tokens = login(client, "meera@x.edu")
	resp = client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
	assert resp.status_code == 200
	body = resp.json()
	assert body["role"] == "supervisor"
	assert body["supervisor_id"] == str(trio.supervisor_id)


def test_unauthenticated_request_rejected(client):
	resp = client.get("/api/v1/scholars")
	assert resp.status_code == 401
	assert resp.json()["error"]["code"] == "unauthenticated"


def test_refresh_rotates_single_use(client, trio):
	tokens = login(client, "a@x.edu")
	first = tokens["refresh_token"]

	resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
	assert resp.status_code == 200
	second = resp.json()["refresh_token"]
	assert second != first

	# replaying the consumed token must fail loudly
	resp = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
	assert resp.status_code == 401
	assert resp.json()["error"]["code"] == "invalid_refresh_token"

	resp = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
	assert resp.status_code == 200


def test_logout_revokes_refresh_token(client, trio):
	tokens = login(client, "a@x.edu")
	resp = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
	assert resp.status_code == 204
	resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
	assert resp.status_code == 401


def test_register_is_admin_only(client, trio):
	scholar = login(client, "a@x.edu")
	resp = client.post(
		"/api/v1/auth/register",
		json={"email": "new@x.edu", "password": "longpassword1", "full_name": "New", "role": "scholar"},
		headers=auth_headers(scholar["access_token"]),
	)
	assert resp.status_code == 403

	admin = login(client, "admin@x.edu")
	resp = client.post(
		"/api/v1/auth/register",
		json={"email": "new@x.edu", "password": "longpassword1", "full_name": "New", "role": "scholar"},
		headers=auth_headers(admin["access_token"]),
	)
	assert resp.status_code == 201

	# duplicate email → mapped 409, not a raw 500
	resp = client.post(
		"/api/v1/auth/register",
		json={"email": "new@x.edu", "password": "longpassword1", "full_name": "New", "role": "scholar"},
		headers=auth_headers(admin["access_token"]),
	)
	assert resp.status_code == 409
	assert resp.json()["error"]["code"] == "duplicate_email"