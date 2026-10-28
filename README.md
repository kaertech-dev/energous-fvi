# energous-fvi

## Configuration

In PowerShell, create `.env` in the project root by running
`Copy-Item .env.example .env`. Set a unique `SECRET_KEY`, a strong
`ADMIN_PASSWORD`, and the database connection values; do not leave the example
placeholders or required database values blank. The app loads this file
automatically when started with Python or Docker Compose and exits during
startup if any required value is missing.

For local development, install dependencies with `pip install -r requirements.txt`
and start with `python run.py`. To run in Docker, use `docker compose up --build`.
The container uses Gunicorn and stores timestamps in the `Asia/Manila` timezone.
Gunicorn runs two workers, and MySQL connections use five-second connect, read,
and write timeouts by default. Scan write transactions allow up to 15 seconds
for the database response, and admin reads allow up to 20 seconds. If a database
operation times out, API requests return HTTP 503 with a retry message rather
than waiting for the Gunicorn worker timeout. Production-sized admin query
performance still needs validation against the deployment database.
This app reads and writes the production `energous.esense_main` and
`energous.esense_fvi` tables.

Before recording a final inspection, the unit must have passed `progtest`,
`assembly`, `lasermarking1`, `vi`, `ft1`, `ft2`, and `lasermarking2`. Operator
FAILs are limited to three attempts; a fourth operator FAIL is not accepted.
FAIL and mismatch rows share an incrementing serial suffix and matching
`test_rep`, so mismatch records can cause later rows to use suffixes above `_3`.

Prog ID/serial mismatches are logged to `esense_fvi` with the scanned and
expected prog IDs in `remarks`, status `0`, and the next shared serial suffix
and `test_rep`. Mismatches do not consume the three operator FAIL attempts;
from test repetition 3 onward the scan warns operators to escalate to FA but
blocks the current scan from reaching PASS/FAIL. The operator must correct the
scan and verify the matching prog ID and serial before continuing.