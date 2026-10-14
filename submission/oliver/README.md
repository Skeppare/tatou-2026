# Oliver – Fuzzing

My specialization was fuzzing the Tatou API. The purpose was to test how the server handles unexpected and malformed inputs and identify potential security issues.

The group's GitHub history includes API fuzzing tests and fixes related to malformed JSON handling. These changes were followed by additional fixes after merging.

I also added a regression test in commit `c1e20c4` for the `/api/delete-document/1` endpoint. The test checks that an unauthenticated DELETE request returns HTTP 401.

The test is located in `server/test/test_api.py`. Run from `server` with the virtual environment activated:

```bash
python -m pytest test/test_api.py -v
```

Both API tests in the local version passed on 2026-10-14.

The regression test verifies authentication handling, while the fuzzing work focuses on how the API handles invalid inputs.
