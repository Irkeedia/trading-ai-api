def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_health_has_request_id_header(client):
    r = client.get("/api/health")
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}


def test_openapi_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_engine_control_requires_api_key(client):
    r = client.post("/api/engine/control", json={"action": "stop"})
    assert r.status_code == 401


def test_engine_control_accepts_api_key(client):
    r = client.post(
        "/api/engine/control",
        json={"action": "stop"},
        headers={"X-API-Key": "pytest-api-secret-not-for-prod"},
    )
    assert r.status_code in (200, 503)


def test_exchange_keys_requires_api_key(client):
    r = client.get("/api/exchange/keys", params={"email": "test@example.com"})
    assert r.status_code == 401
