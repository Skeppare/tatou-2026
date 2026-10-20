from itsdangerous import URLSafeTimedSerializer
from unittest.mock import MagicMock
from flask import g
from server import app
import io

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


def test_upload_document_when_filename_not_empty():
    view = app.view_functions["upload_document"]

    with app.test_request_context(
        "/api/upload-document",
        method="POST",
        data={"file":(io.BytesIO(b"not a pdf"), "test.pdf", "text/plain")},
        content_type="multipart/form-data", 
    ):
        response, status = view.__wrapped__()

    assert status == 400
    assert response.get_json()["error"] == "invalid file type"


def test_get_document_returns_404_when_not_owned(monkeypatch):
    engine = MagicMock()

    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = None

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    with app.test_request_context(
        "/api/get-document/13"):
        g.user = {"id":31}
        response, status = app.view_functions["get_document"].__wrapped__(13)

    assert status == 404
    assert response.get_json()["error"] == "document not found"


def test_create_user_requires_fields():
    client = app.test_client()

    response = client.post(
        "/api/create-user",
        json={}
    )

    assert response.status_code == 400
    assert "error" in response.get_json()

def test_login_requires_credentials():
    client = app.test_client()

    response = client.post(
        "/api/login",
        json={}
    )

    assert response.status_code == 400
    assert "error" in response.get_json()

def test_list_documents_requires_authentication():
    client = app.test_client()

    response = client.get("/api/list-documents")

    assert response.status_code == 401

def test_list_versions_requires_authentication():
    client = app.test_client()

    response = client.get("/api/list-versions")

    assert response.status_code == 401

def test_list_versions_by_id_requires_authentication():
    client = app.test_client()

    response = client.get("/api/list-versions/1")

    assert response.status_code == 401

def test_list_all_versions_requires_authentication():
    client = app.test_client()

    response = client.get("/api/list-all-versions")

    assert response.status_code == 401

def test_get_document_without_id_requires_authentication():
    client = app.test_client()

    response = client.get("/api/get-document")

    assert response.status_code == 401

def test_delete_document_without_id_requires_authentication():
    client = app.test_client()

    response = client.delete("/api/delete-document")

    assert response.status_code == 401

def test_delete_document_post_requires_authentication():
    client = app.test_client()

    response = client.post("/api/delete-document", json={"id": 1})

    assert response.status_code == 401

def test_read_watermark_requires_authentication():
    client = app.test_client()

    response = client.post("/api/read-watermark", 
                           json={
                               "id": 1,
                               "method":"toy-eof",
                               "key":"test"
                               }
                            )
    

    assert response.status_code == 401

def test_read_watermark_by_id_requires_authentication():
    client = app.test_client()

    response = client.post("/api/read-watermark/1", 
                           json={
                               "method":"toy-eof",
                               "key":"test"
                               }
                            )
    

    assert response.status_code == 401
