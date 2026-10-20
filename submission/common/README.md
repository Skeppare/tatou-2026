# Shared report

## Test coverage

The test suite was run on 2026-10-20 using Python 3.12.3. The complete test suite finished successfully with 69 test passed, 12 skipped, and no failures. 

The test suite includes unit tests for the watermarking methods, API tests, fuzzing tests, and RMAP protocol tests. Additional API route tests were added to ensure that the applications API endpoints are exercised by the test suite. The RMAP tests were also updated to match the current watermarking implementation and test configuration. 

An HTML coverage report can be generated from the server directory with:

python -m pip install pytest-cov
python -m pytest --cov=src --cov-report=html

The generated report is stored in:
server/htmlcov/
with  htmlcov/index.html as the main report page. 

To run the complete test suite without generating coverage:
python -m pytest -q

## Mapping between specifications and tests

The table follows the requirements in `Platform_specifications.md` and links them to the existing unit, API, and RMAP tests. Some tests cover only part of a requirement.

1. **Upload documents**  
   Covered by API and mutation tests for the upload route.  
   Coverage: Partial

2. **Only owners can access originals**  
   Covered by authentication and access-control tests for document retrieval.  
   Coverage: Partial

3. **Generate watermarked versions**  
   Covered by watermarking unit tests, API tests, and RMAP tests.  
   Coverage: Tested

4. **Watermarks are hard to remove**  
   Not directly verified by the automated test suite.  
   Coverage: Not tested

5. **Owner can retrieve the secret/version**  
   Covered by watermark round-trip tests and API route tests.  
   Coverage: Partial

6. **Create unguessable secret links**  
   RMAP tests verify link generation and protocol behaviour, but do not directly prove cryptographic unguessability.  
   Coverage: Partial

7. **Download using a shared link**  
   Covered by RMAP and version-related tests.  
   Coverage: Partial

8. **Keep original metadata confidential**  
   Not directly verified by the automated test suite.  
   Coverage: Not tested

9. **Documents available to owner**  
   Covered by API tests for document access.  
   Coverage: Partial

10. **Owner can delete documents**  
    API tests verify authentication and deletion access control.  
    Coverage: Partial

11. **Third parties cannot modify documents**  
    Covered by authentication and access-control tests.  
    Coverage: Partial





The suite also contains tests for the health endpoint, user creating and login validation, document/version listing, watermark creation and reading, RMAP handshakes, malformed RMAP messages, replay/session handling, missing configuration, and failure handling.