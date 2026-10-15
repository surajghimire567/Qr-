# Day 6 test evidence

**Run date:** 15 October 2026

**Runtime:** Python 3.14.4, Django 6.1.1, requests 2.34.2, Pillow 12.3.0

**Database used by tests:** Django's isolated in-memory SQLite test database

**Provider requests:** mocked; no live or sandbox payment was initiated

## Automated commands

The shell environment contains a `DEBUG` value that is not a valid boolean, so each Django command below was run with a valid per-process value. The private `.env` file was not changed.

| Command | Result |
| --- | --- |
| `$env:DEBUG = 'True'; .\.venv\Scripts\python.exe manage.py check` | Passed; no system-check issues. |
| `$env:DEBUG = 'True'; .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` | Passed; no model/migration drift. |
| `$env:DEBUG = 'True'; .\.venv\Scripts\python.exe manage.py test --verbosity 1` | Passed; 55 tests discovered and 55 passed. |
| `$env:DEBUG = 'True'; .\.venv\Scripts\python.exe manage.py test accounts store cart orders payments --verbosity 1` | Passed; the same 55 tests discovered and passed. |
| `.\.venv\Scripts\python.exe -m pip check` | Passed; no broken requirements. |

The test runner applied the migrations to its isolated test database, including the preflight checks for nonnegative amounts and positive item quantities. The workspace `db.sqlite3` was not migrated or otherwise modified. The mutating `test_checkout.py` script was not run.

## Coverage represented by the automated tests

- Default test discovery includes all five app suites.
- Checkout price snapshots, conditional stock decrement, rollback on insufficient stock, and repeated checkout-key submission.
- Exactly-once stock release, cancellation and payment-start guards, order ownership, POST-only actions, and CSRF enforcement.
- Account history login/owner isolation, newest-first pagination, 0/1/10/11-order boundaries, and invalid, negative, and too-large page values.
- Khalti start claims, server lookup, reference preservation, amount/reference mismatches, duplicate callback handling, and uncertain initiation.
- eSewa signed callback checks, independent server status lookup, non-finite amount rejection, status-check method enforcement, and failure/`NOT_FOUND` holds.
- Read-only order admin controls, separate customer/admin session behavior, POST logout isolation, and idempotent synthetic demo seeding.

## Not performed

- Manual browser flow, responsive layout inspection, keyboard-only pass, and screenshot capture.
- Any Khalti or eSewa sandbox transaction, including a real UAT user login.
- Fresh-clone installation and migration against a new on-disk database.
- PostgreSQL concurrency tests or production deployment checks.
- Institution template/rubric review and student-specific report fields.

Capture genuine redacted UI and sandbox evidence separately before representing those items as complete. See [the screenshot evidence guide](screenshots/README.md) and [the demo script](demo-script.md).
