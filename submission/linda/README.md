# Linda - Mutation testing
I worked with mutation testing on the Tatou server using Cosmic Ray.

Changes:
The mutation testing configuration is located in: 
    server/cosmic-ray.toml

The tests added as a result of the mutation testing are located in:
    server/test/test_api.py

I also added pythonpath = ["src"] to:
    server/pyproject.toml

so that pytest and Cosmic Ray can correcly import the server module.

The main mutation-testing changes were introduced in commit: 
     0b4cfe7 Add mutation testing with Cosmic Ray

Running the mutation tests:

First verify that the normal test suite passes: 
    pytest test/test_api.py

Then create and execute a Cosmic Ray session:
    cosmic-ray init cosmic-ray.toml session.sqlite
    cosmic-ray exec cosmic-ray.toml session.sqlite

Results can be inspected using:
    cr-report session.sqlite

Mutation testing results:
Two surviving mutants were selected for further analysis

1. Upload document filename validation
Cosmic Ray changed: 
    if not file or file.filename == "":
to
    if not file or file.filename != "":

The existing tests did not detect this change, so the mutant initially survived. 
I added a test that uploads a file with a non-empty filename and verifies that it passes the filename check and reaches the MIME-type validation. 

After adding the test, the mutant was killed
    core/ReplaceComparisonOperator_Eq_NotEq 0
    TestOutcome.KILLED

2. Document ownership lookup
Cosmic Ray changed:
    if not row:
to
    if row:

The wxisting tests did not detect this mutation.
I added a test using a mocked database engine where the document lookup returns no row, representing an authenticated user requesting a document they do not own. The correct implementation must return 404 document not found. 

After adding the test, the mutant was killed:
    core/ReplaceUnaryOperator_Delete_Not 12
    TestOutcome.KILLED
