from fastapi.testclient import TestClient

from strix_console_service.app import create_app

ACCESS_TOKEN = "test-access-token"
BOOTSTRAP_TOKEN = "test-bootstrap-token"


def test_health_requires_access_token() -> None:
    client = TestClient(create_app(access_token=ACCESS_TOKEN, bootstrap_token=BOOTSTRAP_TOKEN))

    unauthorized = client.get("/api/health")
    authorized = client.get(
        "/api/health",
        headers={"X-Strix-Access-Token": ACCESS_TOKEN},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {
        "status": "ok",
        "serviceVersion": "0.1.0",
        "schemaVersion": 1,
        "platform": "windows",
    }


def test_bootstrap_token_can_only_be_exchanged_once() -> None:
    client = TestClient(create_app(access_token=ACCESS_TOKEN, bootstrap_token=BOOTSTRAP_TOKEN))
    headers = {"X-Strix-Bootstrap": BOOTSTRAP_TOKEN}

    first = client.post("/api/session", headers=headers)
    second = client.post("/api/session", headers=headers)

    assert first.status_code == 200
    assert first.json() == {"accessToken": ACCESS_TOKEN}
    assert second.status_code == 401
