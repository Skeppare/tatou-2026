"""Real PGP handshakes and PDF publication, with an isolated SQLite test DB.

SQLite's LAST_INSERT_ID shim exercises the existing SQL pipeline; deployment
still uses MariaDB. All test keys and PDFs are generated in pytest temp dirs.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import secrets

import pymupdf
import pytest
from itsdangerous import URLSafeTimedSerializer
from rmap import RMAPClient
from rmap.crypto import encrypt_json
from rmap.keygen import generate_keypair
from sqlalchemy import create_engine, event, text

import watermarking_utils as wm


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    root = tmp_path_factory.mktemp("rmap-keys")
    clients = root / "clients"
    clients.mkdir()
    for identity in ("server", "Group_01", "Group_02"):
        key = generate_keypair(identity, f"{identity}@example.test")
        (root / f"{identity}_priv.asc").write_text(str(key), encoding="ascii")
        (root / f"{identity}_pub.asc").write_text(str(key.pubkey), encoding="ascii")
        if identity != "server":
            (clients / f"{identity}.asc").write_text(str(key.pubkey), encoding="ascii")
    (clients / "README.txt").write_text("Not a key; must be ignored")
    return root


@pytest.fixture
def app(tmp_path, monkeypatch, keys):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    from server import create_app

    application = create_app()
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def sqlite_functions(dbapi, _):
        dbapi.create_function("LAST_INSERT_ID", 0, lambda: dbapi.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0])

    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Synthetic confidential document")
        pdf.save(tmp_path / "assigned.pdf")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE Documents (id INTEGER PRIMARY KEY, name TEXT, path TEXT)"))
        conn.execute(text("""CREATE TABLE Versions (
            id INTEGER PRIMARY KEY, documentid INTEGER NOT NULL, link TEXT UNIQUE NOT NULL,
            intended_for TEXT, secret TEXT NOT NULL, method TEXT NOT NULL, position TEXT, path TEXT NOT NULL
        )"""))
        conn.execute(text("INSERT INTO Documents VALUES (1, 'assigned.pdf', :path)"),
                     {"path": str(tmp_path / "assigned.pdf")})
    application.config.update(
        TESTING=True, _ENGINE=engine, SECRET_KEY=secrets.token_hex(32),
        RMAP_SERVER_PUBLIC_KEY_PATH=str(keys / "server_pub.asc"),
        RMAP_SERVER_PRIVATE_KEY_PATH=str(keys / "server_priv.asc"),
        RMAP_SERVER_KEY_PASSPHRASE=None,
        RMAP_CLIENT_KEYS_DIR=str(keys / "clients"), RMAP_DOCUMENT_ID="1",
    )
    yield application
    engine.dispose()


def client_for(keys, identity="Group_01"):
    return RMAPClient(identity, keys / f"{identity}_priv.asc", keys / "server_pub.asc")


def initiate(app, keys, identity="Group_01", prefix="/api"):
    client = client_for(keys, identity)
    response = app.test_client().post(f"{prefix}/rmap-initiate", json=client.build_msg1())
    assert response.status_code == 200
    assert set(response.json) == {"payload"}
    client.process_resp1(response.json)
    return client


def versions(app):
    with app.config["_ENGINE"].connect() as conn:
        return conn.execute(text("SELECT * FROM Versions ORDER BY id")).mappings().all()


@pytest.mark.parametrize("prefix", ["/api", ""])
def test_handshake_publishes_group_specific_pdf(app, keys, prefix):
    original = (app.config["STORAGE_DIR"] / "assigned.pdf").read_bytes()
    for identity in ("Group_01", "Group_02"):
        client = initiate(app, keys, identity, prefix)
        response = app.test_client().post(f"{prefix}/rmap-get-link", json=client.build_msg2())
        assert response.status_code == 200
        link = client.process_resp2(response.json)
        assert link == client.expected_link and len(link) == 32
        row = versions(app)[-1]
        assert row["link"] == link and row["intended_for"] == identity
        assert row["documentid"] == 1 and row["method"] == "invisible-text"
        download = app.test_client().get(f"/api/get-version/{link}")
        assert download.status_code == 200
        assert wm.read_watermark("invisible-text", download.data, "") == row["secret"]
        download.close()
    first, second = versions(app)
    assert first["path"] != second["path"]
    assert first["secret"] != second["secret"]
    assert (app.config["STORAGE_DIR"] / "assigned.pdf").read_bytes() == original


def test_link_zero_padding(app, keys):
    client = client_for(keys)
    client.nonceClient = 1
    message = encrypt_json({"identity": "Group_01", "nonceClient": 1}, client.serverPublicKey)
    response = app.test_client().post("/api/rmap-initiate", json=message)
    client.process_resp1(response.json)
    response = app.test_client().post("/api/rmap-get-link", json=client.build_msg2())
    assert client.process_resp2(response.json) == f"{1:016x}{client.nonceServer:016x}"


@pytest.mark.parametrize("endpoint", ["rmap-initiate", "rmap-get-link"])
@pytest.mark.parametrize("body", [[], {}, {"payload": 3}, {"payload": "not base64!"}])
def test_malformed_wire_message(app, endpoint, body):
    response = app.test_client().post(f"/api/{endpoint}", json=body)
    assert response.status_code == 400
    assert "payload" not in response.json
    assert versions(app) == []


@pytest.mark.parametrize("nonce", [None, True, -1, 2**64, 1.5, "1", []])
@pytest.mark.parametrize("endpoint,field", [
    ("rmap-initiate", "nonceClient"), ("rmap-get-link", "nonceServer"),
])
def test_invalid_decrypted_nonce(app, keys, nonce, endpoint, field):
    client = client_for(keys)
    message = encrypt_json({"identity": "Group_01", field: nonce}, client.serverPublicKey)
    response = app.test_client().post(f"/api/{endpoint}", json=message)
    assert response.status_code == 400
    assert versions(app) == []


@pytest.mark.parametrize("identity", ["Unknown", "../Group_01", "Group_01.asc", None, []])
def test_unknown_or_invalid_identity(app, keys, identity):
    client = client_for(keys)
    message = encrypt_json({"identity": identity, "nonceClient": 1}, client.serverPublicKey)
    assert app.test_client().post("/api/rmap-initiate", json=message).status_code == 400


def test_no_session_replaced_session_and_replay(app, keys):
    client = client_for(keys)
    message = encrypt_json({"nonceServer": 1}, client.serverPublicKey)
    assert app.test_client().post("/api/rmap-get-link", json=message).status_code == 400
    old = initiate(app, keys)
    current = initiate(app, keys)
    assert app.test_client().post("/api/rmap-get-link", json=old.build_msg2()).status_code == 400
    message = current.build_msg2()
    assert app.test_client().post("/api/rmap-get-link", json=message).status_code == 200
    path = Path(versions(app)[0]["path"])
    contents = path.read_bytes()
    assert app.test_client().post("/api/rmap-get-link", json=message).status_code == 400
    assert len(versions(app)) == 1 and path.read_bytes() == contents
    assert app.extensions["rmap"].server._nonce_server_index == {}


def test_expired_session(app, keys, monkeypatch):
    client = initiate(app, keys)
    service = app.extensions["rmap"]
    monkeypatch.setattr("rmap_service.time.monotonic", lambda: service._expires["Group_01"] + 1)
    assert app.test_client().post("/api/rmap-get-link", json=client.build_msg2()).status_code == 400
    assert versions(app) == []


@pytest.mark.parametrize("setting", [
    "RMAP_SERVER_PUBLIC_KEY_PATH", "RMAP_SERVER_PRIVATE_KEY_PATH",
    "RMAP_CLIENT_KEYS_DIR", "RMAP_DOCUMENT_ID",
])
def test_missing_configuration(app, setting):
    app.config[setting] = None
    response = app.test_client().post("/api/rmap-initiate", json={})
    assert response.status_code == 503
    assert set(response.json) == {"error"}
    assert app.test_client().get("/api/get-watermarking-methods").status_code == 200


def test_mismatched_keypair(app, keys):
    app.config["RMAP_SERVER_PUBLIC_KEY_PATH"] = str(keys / "Group_01_pub.asc")
    assert app.test_client().post("/api/rmap-initiate", json={}).status_code == 503


@pytest.mark.parametrize("failure", ["watermark", "empty", "write", "insert", "commit"])
def test_failed_publication_returns_no_link_and_can_retry(app, keys, monkeypatch, failure):
    client = initiate(app, keys)
    message = client.build_msg2()
    engine = app.config["_ENGINE"]

    def fail(*args, **kwargs):
        raise RuntimeError("sensitive internal detail")

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO Versions" in statement:
            fail()

    with monkeypatch.context() as patch:
        if failure == "watermark":
            patch.setattr(wm, "apply_watermark", fail)
        elif failure == "empty":
            patch.setattr(wm, "apply_watermark", lambda **kwargs: b"")
        elif failure == "write":
            original_open = Path.open

            def fail_write(path, mode="r", *args, **kwargs):
                if mode == "xb":
                    raise OSError("sensitive internal detail")
                return original_open(path, mode, *args, **kwargs)

            patch.setattr(Path, "open", fail_write)
        elif failure == "insert":
            event.listen(engine, "before_cursor_execute", fail_insert)
        else:
            event.listen(engine, "commit", fail)
        try:
            response = app.test_client().post("/api/rmap-get-link", json=message)
        finally:
            if failure == "insert":
                event.remove(engine, "before_cursor_execute", fail_insert)
            if failure == "commit":
                event.remove(engine, "commit", fail)
    assert response.status_code == 503
    assert set(response.json) == {"error"}
    assert "sensitive" not in response.get_data(as_text=True)
    assert versions(app) == []
    assert not list(app.config["STORAGE_DIR"].glob("watermarks/*.pdf"))
    assert app.test_client().get(f"/api/get-version/{client.expected_link}").status_code == 404
    assert app.test_client().post("/api/rmap-get-link", json=message).status_code == 200
    assert len(versions(app)) == 1


def test_existing_output_is_never_overwritten_or_deleted(app, keys):
    client = initiate(app, keys)
    directory = app.config["STORAGE_DIR"] / "watermarks"
    directory.mkdir()
    path = directory / f"rmap_{client.expected_link}.pdf"
    path.write_bytes(b"existing file")
    response = app.test_client().post("/api/rmap-get-link", json=client.build_msg2())
    assert response.status_code == 503
    assert path.read_bytes() == b"existing file"
    assert versions(app) == []


def test_existing_watermark_route_uses_shared_pipeline(app):
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps(
        {"uid": 1, "login": "owner", "email": "owner@example.test"}
    )
    response = app.test_client().post("/api/create-watermark/1", json={
        "method": "toy-eof", "intended_for": "reader", "position": "",
        "secret": "synthetic watermark", "key": "synthetic test key",
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201
    assert response.json["filename"] == "assigned__reader.pdf"
    row = versions(app)[0]
    assert row["link"] == response.json["link"]
    assert wm.read_watermark("toy-eof", row["path"], "synthetic test key") == "synthetic watermark"


def test_concurrent_message2_publishes_only_once(app, keys):
    client = initiate(app, keys)
    message = client.build_msg2()

    def complete():
        with app.test_client() as http:
            return http.post("/api/rmap-get-link", json=message).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: complete(), range(2)))
    assert sorted(statuses) == [200, 400]
    assert len(versions(app)) == 1


@pytest.mark.parametrize("failure", ["missing_record", "missing_file", "invalid_pdf"])
def test_unavailable_assigned_document(app, keys, failure):
    if failure == "missing_record":
        app.config["RMAP_DOCUMENT_ID"] = "999"
    elif failure == "missing_file":
        (app.config["STORAGE_DIR"] / "assigned.pdf").unlink()
    else:
        (app.config["STORAGE_DIR"] / "assigned.pdf").write_bytes(b"not a PDF")
    client = initiate(app, keys)
    response = app.test_client().post("/api/rmap-get-link", json=client.build_msg2())
    assert response.status_code == 503
    assert set(response.json) == {"error"}
    assert versions(app) == []


def test_passphrase_protected_server_key(app, keys, tmp_path):
    passphrase = secrets.token_hex(16)
    key = generate_keypair("Protected server", "server@example.test", passphrase)
    private_path, public_path = tmp_path / "server_priv.asc", tmp_path / "server_pub.asc"
    private_path.write_text(str(key), encoding="ascii")
    public_path.write_text(str(key.pubkey), encoding="ascii")
    app.config.update(RMAP_SERVER_PRIVATE_KEY_PATH=str(private_path),
                      RMAP_SERVER_PUBLIC_KEY_PATH=str(public_path),
                      RMAP_SERVER_KEY_PASSPHRASE=passphrase)
    client = RMAPClient("Group_01", keys / "Group_01_priv.asc", public_path)
    response = app.test_client().post("/api/rmap-initiate", json=client.build_msg1())
    assert response.status_code == 200
    client.process_resp1(response.json)
    response = app.test_client().post("/api/rmap-get-link", json=client.build_msg2())
    assert response.status_code == 200
    assert client.process_resp2(response.json) == client.expected_link
