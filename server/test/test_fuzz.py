
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hypothesis import given, settings, strategies as st
from itsdangerous import URLSafeTimedSerializer
from server import create_app


@settings(max_examples=100, deadline=None)
@given(payload=st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.text(max_size=100),
    st.lists(st.integers(), max_size=10),
    st.dictionaries(
        st.text(max_size=20),
        st.one_of(st.none(), st.integers(), st.text(max_size=100)),
        max_size=10,
    ),
))
def test_create_watermark_fuzz(payload):
    app = create_app()
    app.config["TESTING"] = True

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )

    token = serializer.dumps({
        "uid": 999999,
        "login": "fuzz_test",
        "email": "fuzz@example.invalid",
    })

    client = app.test_client()

    response = client.post(
        "/api/create-watermark/999999",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code != 500, (
        f"Unexpected server error for payload: {payload!r}"
    )

@settings(max_examples=100, deadline=None)
@given(payload=st.one_of(
    st.booleans(),
    st.integers(),
    st.text(max_size=100),
    st.lists(st.integers(), max_size=10),
))
def test_create_watermark_body_id_fuzz(payload):
    app = create_app()
    app.config["TESTING"] = True

    serializer = URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="tatou-auth",
    )
    token = serializer.dumps({
        "uid": 999999,
        "login": "fuzz_test",
        "email": "fuzz@example.invalid",
    })

    response = app.test_client().post(
        "/api/create-watermark",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400, (
        f"Unexpected status {response.status_code} for {payload!r}"
    )
