# Shared report

## Test coverage

The tests were run on 2026-10-14 using Python 3.13.13 and commit `c1e20c4`. Eight tests passed and three were skipped. No tests failed. The skipped tests were for `invisible-text`, which could not use the sample PDF.

The tests covered **32% of the code** (252 of 796 statements). This leaves much of the application untested.

To run the same check, activate the virtual environment and run these commands from `server`:

```bash
python -m pip install -e ".[dev]" pytest-cov
python -m pytest -rs --cov=src --cov-report=term-missing
```

## Mapping between specifications and tests

The table follows the requirements in [Platform_specifications.md](../../Platform_specifications.md) and links them to the existing [unit tests](../../server/test/test_watermarking_all_methods.py) and [API tests](../../server/test/test_api.py). Some tests only check part of a requirement.

| Requirement | Test | Coverage of requirement |
| --- | --- | --- |
| 1. Upload documents | None | Not tested |
| 2. Only owners can access originals | None | Not tested |
| 3. Generate watermarked versions | `test_is_watermark_applicable`, `test_add_watermark_and_shape` | Partial: method-level checks |
| 4. Watermarks are hard to remove | None | Not tested |
| 5. Owner can retrieve the secret/version | `test_read_secret_roundtrip` | Partial: secret recovery, not ownership/version access |
| 6. Create unguessable secret links | None | Not tested |
| 7. Download using a shared link | None | Not tested |
| 8. Keep original metadata confidential | None | Not tested |
| 9. Documents available to owner | None | Not tested |
| 10. Owner can delete documents | None | Not tested |
| 11. Third parties cannot modify documents | `test_delete_document_requires_authentication` | Partial: anonymous deletion returns 401 |

There is also a health check test, `test_healthz_route`. It checks the status code and JSON response, but does not check whether the database is connected. These results are for the local version above; the newer changes on GitHub are not included.
