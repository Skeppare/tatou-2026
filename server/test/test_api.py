from itsdangerous import URLSafeTimedSerializer
from server import app

def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.is_json
    
def test_delete_document_requires_authentication():
    client = app.test_client()

    resp = client.delete("/api/delete-document/1")

    assert resp.status_code == 401

def test_get_document_requires_authentication():
    client = app.test_client()

    resp = client.get("/api/get-document/1")

    assert resp.status_code == 401
    assert resp.is_json
    assert resp.get_json()["error"] == "Missing or invalid Authorization header"


def test_create_watermark_rejects_invalid_json():
    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth"
    )
    token = serializer.dumps({
        "uid": 999999,
        "login": "fuzz_test",
        "email": "fuzz@example.invalid"
    })

    client = app.test_client()

    response = client.post(
        "/api/create-watermark/999999",
        json=True,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body must be an object"


def test_create_watermark_body_id_rejects_invalid_json():
    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth"
    )

    token = serializer.dumps({
        "uid": 999999,
        "login": "fuzz_test",
        "email": "fuzz@example.invalid"
    })

    response = app.test_client().post(
        "/api/create-watermark",
        json=True,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body must be an object"
