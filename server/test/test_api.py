from itsdangerous import URLSafeTimedSerializer
from unittest.mock import MagicMock
from flask import g
from server import app
from types import SimpleNamespace
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
                               "method":"invisible-text",
                               "key":"test"
                               }
                            )
    

    assert response.status_code == 401

def test_read_watermark_by_id_requires_authentication():
    client = app.test_client()

    response = client.post("/api/read-watermark/1", 
                           json={
                               "method":"invisible-text",
                               "key":"test"
                               }
                            )
    

    assert response.status_code == 401

def test_get_document_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = MagicMock()
    row.path = str(pdf_path)
    row.name = "owned.pdf"
    row.sha256 = "abc123"

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    with app.test_request_context(
        "/api/get-document/1"):
        g.user = {"id": 1}
        response = app.view_functions["get_document"].__wrapped__(1)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_delete_document_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = MagicMock()
    row.id = 1
    row.path = str(pdf_path)

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    with app.test_request_context(
        "/api/delete-document/1",
        method = "DELETE"
        ):
        g.user = {"id": 1}
        response, status = app.view_functions["delete_document"].__wrapped__(1)

    assert status == 200

    data = response.get_json()
    assert data["deleted"] is True
    assert data["id"] == 1
    assert data["file_deleted"] is True
    assert not pdf_path.exists()

def test_read_watermark_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = MagicMock()
    row.id = 1
    row.name = "owned.pdf"
    row.path = str(pdf_path)

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    monkeypatch.setattr("server.WMUtils.read_watermark", lambda method, pdf, key: "synthetic secret")

    with app.test_request_context(
        "/api/read-watermark/1",
        method="POST",
        json={
            "method": "invisible-text",
            "key": "test-key"
        }
    ):
        g.user = {"id": 1}
        response, status = app.view_functions["read_watermark"].__wrapped__(1)

    assert status == 201

    data = response.get_json()
    assert data["documentid"] == 1
    assert data["secret"] == "synthetic secret"
    assert data["method"] == "invisible-text"

def test_list_documents_success(monkeypatch):
    row = SimpleNamespace(id=1, name="owned.pdf", creation="2026-10-20T12:00:00", sha256_hex="ABC123", size=123)

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.all.return_value = [row]

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
        "uid": 1,
        "login": "owner",
        "email": "owner@example.test"
    })

    response = app.test_client().get(
        "/api/list-documents",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.get_json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == 1
    assert data["documents"][0]["name"] == "owned.pdf"


def test_list_versions_success(monkeypatch):
    row = SimpleNamespace(id=10, documentid=1, link="test-link", intended_for="Group_01", secret="test_secret", method="invisible-text"
    )

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.all.return_value = [row]

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
        "uid": 1,
        "login": "owner",
        "email": "owner@example.test"
    })

    response = app.test_client().get(
        "/api/list-versions/1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.get_json()
    assert len(data["versions"]) == 1
    assert data["versions"][0]["id"] == 10
    assert data ["versions"][0]["secret"] == "test_secret"

def test_list_versions_query_parameter_success(monkeypatch):
    row = SimpleNamespace(id=10, documentid=1, link="test-link", intended_for="Group_01", secret="test_secret", method="invisible-text"
    )
    
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.all.return_value = [row]

    monkeypatch.setitem(app.config, "_ENGINE", engine)  

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
        "uid": 1,
        "login": "owner",
        "email": "owner@example.test"
    })

    response = app.test_client().get(
        "/api/list-versions?id=1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.get_json()["versions"]) == 1

def test_list_all_versions_success(monkeypatch):
    row = SimpleNamespace(id=10, documentid=1, link="test-link", intended_for="Group_01", method="invisible-text"
    )

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.all.return_value = [row]

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
        "uid": 1,
        "login": "owner",
        "email": "owner@example.test"
    })

    response = app.test_client().get(
        "/api/list-all-versions",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.get_json()
    assert len(data["versions"]) == 1
    assert data["versions"][0]["documentid"] == 1   
    assert data["versions"][0]["link"] == "test-link"


def test_get_watermarking_methods_success():
    response = app.test_client().get("/api/get-watermarking-methods")

    assert response.status_code == 200

    data = response.get_json()
    assert "methods" in data
    assert "count" in data
    assert data["count"] == len(data["methods"])


def test_create_user_success(monkeypatch):
    insert_result = MagicMock()
    insert_result.lastrowid = 1

    user_row = SimpleNamespace(id=1, email="owner@example.test", login="owner")

    conn= MagicMock()
    conn.execute.side_effect = [
        insert_result,  
        MagicMock(one=MagicMock(return_value=user_row))
     ]  

    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    response = app.test_client().post(
        "/api/create-user",
        json={
            "email": "owner@example.test",
            "login": "owner",
            "password": "test-password"
        }
    )

    assert response.status_code == 201

    data = response.get_json()
    assert data["id"] == 1
    assert data["email"] == "owner@example.test"
    assert data["login"] == "owner"


def test_login_success(monkeypatch):
    user_row = SimpleNamespace(id=1, email="owner@example.test", login="owner", hpassword="fake-hash")

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = user_row

    monkeypatch.setitem(app.config, "_ENGINE", engine)

    monkeypatch.setattr("server.check_password_hash", lambda stored_hash, password: True)


    response = app.test_client().post(
        "/api/login",
        json={
            "email": "owner@example.test",
            "password": "test-password"
        }
    )

    assert response.status_code == 200

    data = response.get_json()
    assert "token" in data
    assert data ["token_type"] == "bearer"

def test_upload_document_success(monkeypatch, tmp_path):
    row = SimpleNamespace(id=1, name="uploaded.pdf", creation="2026-10-20T12:00:00", sha256_hex="ABC123", size=20)

    conn = MagicMock()

    # 1. INSERT INTO Documents
    # 2. SELECT LAST_INSERT_ID()
    # 3. SELECT document row
    insert_result = MagicMock()
    last_id_result = MagicMock()
    last_id_result.scalar.return_value = 1
    select_result = MagicMock()
    select_result.one.return_value = row

    conn.execute.side_effect = [
        insert_result,  
        last_id_result,  
        select_result  
    ]
    
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
        "uid": 1,
        "login": "owner",
        "email": "owner@example.test"
    })

    response = app.test_client().post(
        "/api/upload-document",
        data={
            "name": "uploaded.pdf",
            "file": (io.BytesIO(b"%PDF-1.4\n% test pdf\n"), "uploaded.pdf", "application/pdf")
        },
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"}    
    )

    assert response.status_code == 201

    data = response.get_json()
    assert data["id"] == 1
    assert data["name"] == "uploaded.pdf"


def test_get_version_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "watermarked.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = SimpleNamespace(
        id=10,
        documentid=1,
        link="test-link",
        intended_for="Group_01",
        path=str(pdf_path)
    )
    
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    response = app.test_client().get(
        "/api/get-version/test-link"
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"

def test_get_document_query_parameter_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = SimpleNamespace(
        path=str(pdf_path),
        name="owned.pdf",
        sha256_hex="ABC123",
        size=20
    )

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row
    
    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
            "uid": 1,
            "login": "owner",
            "email": "owner@example.test" 
    })

    response = app.test_client().get(
        "/api/get-document?id=1",
        headers={"Authorization": f"Bearer {token}"} 
        
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"  


def test_delete_document_body_id_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")

    row = SimpleNamespace(
        id = 1,
        path=str(pdf_path)
    )

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row
    engine.begin.return_value.__enter__.return_value = MagicMock()

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)
    
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
                "uid": 1,
                "login": "owner",
                "email": "owner@example.test" 
        })
    
    response = app.test_client().post(
        "/api/delete-document",
        json={"id":1},
        headers={"Authorization": f"Bearer {token}"} 
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["deleted"] is True
    assert data["id"] == 1
    assert not pdf_path.exists()

def test_read_watermark_body_id_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")
    
    row = SimpleNamespace(
        id = 1,
        name="owned.pdf",
        path=str(pdf_path)
        )
    
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)
    
    monkeypatch.setattr("server.WMUtils.read_watermark", lambda method, pdf, key: "synthetic secret")

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
                    "uid": 1,
                    "login": "owner",
                    "email": "owner@example.test" 
            })
        
    response = app.test_client().post(
            "/api/read-watermark",
            json={"id":1,
                  "method": "invisible-text",
                  "key": "test-key"
                  },
            headers={"Authorization": f"Bearer {token}"} 
    )

    assert response.status_code == 201

    data = response.get_json()
    assert data ["documentid"] == 1
    assert data ["secret"] == "synthetic secret"
    assert data ["method"] == "invisible-text"


def test_delete_document_query_parameter_success(monkeypatch, tmp_path):
    pdf_path = tmp_path / "owned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")
    
    row = SimpleNamespace(
        id = 1,
        path=str(pdf_path)
        )
    
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = row
    engine.begin.return_value.__enter__.return_value = MagicMock()

    monkeypatch.setitem(app.config, "_ENGINE", engine)
    monkeypatch.setitem(app.config, "STORAGE_DIR", tmp_path)
    

    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps({
                    "uid": 1,
                    "login": "owner",
                    "email": "owner@example.test" 
            })
        
    response = app.test_client().delete(
            "/api/delete-document?id=1",
            headers={"Authorization": f"Bearer {token}"} 
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data ["deleted"] is True
    assert int(data["id"]) == 1
    assert not pdf_path.exists()
