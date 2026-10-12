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
This app reads and writes the production `energous.esense_main` and
`energous.esense_fvi` tables.

Before recording a final inspection, the unit must have passed `progtest`,
`assembly`, `lasermarking1`, `vi`, `ft1`, `ft2`, and `lasermarking2`. Failed
inspections are recorded with serial suffixes `_1` through `_3` and matching
`test_rep` values; a fourth FAIL attempt is not accepted.