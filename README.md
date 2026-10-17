# tatou
A web platform for pdf watermarking. This project is intended for pedagogical use, and contain security vulnerabilities. Do not deploy on an open network.

## Instructions

You need Python 3.11 or newer for local development and tests, and Docker with Docker Compose v2 to run the full application. The `http` command used below requires HTTPie.

The following instructions are meant for a bash terminal on a Linux machine. If you are using something else, you will need to adapt them.

To clone the repo, you can simply run:

```bash
git clone https://github.com/nharrand/tatou-2026.git
```

Note that you should probably fork the repo and clone your own repo.


### Run python unit tests

```bash
cd tatou-2026/server

# Create a python virtual environement
python3 -m venv .venv

# Activate your virtual environement
. .venv/bin/activate

# Install the necessary dependencies
python -m pip install -e ".[dev]"

# Run the unit tests
python -m pytest test/test_watermarking_all_methods.py

# Run all tests (including API tests)
python -m pytest
```

### Run API tests

From `server`, with the virtual environment above activated:

```bash
python -m pytest test/test_api.py -v
```

The API tests use Flask's test client to check the health endpoint and that deleting a document without authentication returns HTTP 401. No running HTTP server is needed. These tests do not verify database connectivity: the health endpoint also returns HTTP 200 when the database is unavailable. See [API documentation](server/API.md) for endpoint details.

### Coverage analysis

The measured coverage report, specification-to-test mapping and individual specialization folders are available in [submission/common](submission/common/README.md).

From `server`, with the same virtual environment activated:

```bash
python -m pip install pytest-cov
python -m pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```

This runs all tests and reports source-code coverage. Missing lines appear in the terminal; open `htmlcov/index.html` for the HTML report. `coverage.xml` can be used by CI tools. Review skipped tests as well: skipped tests do not verify the corresponding behavior.

### Deploy

The following starts the full application, including the database and web interface.

From the root of the directory (run `cd ..` if you are still in `server`):

Create or edit `.env` with the following values, replacing the example passwords and flag. There is no `sample.env` in this repository.

```dotenv
MARIADB_ROOT_PASSWORD=replace_with_root_password
MARIADB_USER=tatou
MARIADB_PASSWORD=replace_with_app_password
FLAG_2=replace_with_lab_flag
```

```bash
# Rebuild the docker image and deploy the containers
docker compose up --build -d

# Monitor logs in realtime 
docker compose logs -f

# Test if the API is up
http -v :5000/healthz

# Open your browser at 127.0.0.1:5000 to check if the website is up.
```

Press Ctrl+C to stop following logs; the containers keep running. Check that `/healthz` reports `"db_connected": true` to confirm the database connection.

After code changes, rerun `docker compose up --build -d` to rebuild and deploy. To stop the containers while keeping the database and uploaded files:

```bash
docker compose down
```

The database schema in `db/tatou.sql` is loaded only when the database volume is first initialized. Avoid `docker compose down -v` unless you intend to delete stored data.
