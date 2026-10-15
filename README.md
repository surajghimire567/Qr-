# Qr Shop

Qr Shop is a Django e-commerce academic demo for browsing products, using a cart, checking out, and verifying sandbox payments. The project favors an explainable checkout and payment lifecycle over production-scale fulfilment.

## Features

- Product catalogue with category filtering, stock visibility, and product details.
- Guest carts stored in the browser session and authenticated carts saved per user.
- Account registration, profile details, paginated order history, and owner-only order pages.
- Checkout that snapshots unit prices and reserves stock in one database transaction.
- One guarded payment start per order, with Khalti and eSewa UAT adapters.
- Server-side payment lookup before an order is marked paid.
- Safe cancellation before a payment starts, with exactly-once stock release.
- Read-only order records in Django admin; catalog products and categories remain manageable.
- Synthetic sample catalog and automated tests that mock all payment providers.

## Data model notes

- `OrderItem.price` records the unit price at purchase time, so later catalog changes do not rewrite order history.
- Prices and totals use `DecimalField`; validators and database constraints reject negative amounts.
- A category with products and a product referenced by an order item are protected from deletion.
- Guest carts use the session. Authenticated carts use the `SavedCart` table. There is no general `Cart` table.
- `payment_ref` keeps the provider initiation ID (`pidx` or eSewa transaction UUID). `gateway_transaction_id` stores the final verified receipt.
- `paid` means the provider's server-side status was verified. It does not prove that an order shipped or was delivered.

## Local setup

Use a new clone or a disposable copy of the project for a first run. Existing local `db.sqlite3` files may contain data; take a backup before applying migrations to an existing database.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$env:DEBUG = "True"
```

Set a unique `SECRET_KEY` in `.env`. Keep `.env` private. The sample configuration enables local HTTP and eSewa's UAT endpoint. Khalti stays hidden until `KHALTI_SECRET_KEY` is configured. Verify current sandbox credentials in the providers' official documentation.

If the shell or operating system already defines `DEBUG`, it overrides the `.env` file. Set it to the literal `True` or `False`; values such as `release` are invalid for this boolean setting.

For a fresh local database:

```powershell
python manage.py migrate
python manage.py seed_demo_data
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Register a customer account for the storefront. Use the superuser account at `/admin/` to manage the catalog. The sample seed command is idempotent and creates synthetic products without overwriting rows with the same slugs.

## Configuration

`.env.example` documents the supported values. For local work, use `DEBUG=True`, local `ALLOWED_HOSTS`, and leave `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, and `SECURE_SSL_REDIRECT` false. For an HTTPS deployment, set `DEBUG=False`, use exact allowed hosts, a strong secret, secure cookies, and SSL redirect only after HTTPS is correctly configured. Enable HSTS only after confirming the host is HTTPS-only. Do not use Django's development server as a public production server.

The test suite mocks provider requests; it does not need live payment credentials and never submits a transaction. Do not present a provider callback URL or a mock test as proof of a real payment.

## Verification

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
python -m pip check
```

Tests use Django's isolated test database. `test_checkout.py` is an interactive script that creates an order and reduces stock in the configured database; do not run it against valuable data.

## Lifecycle and current limits

- Checkout reserves stock. Cancellation is available only before any gateway initiation.
- A verified Khalti `Expired` or `User canceled` result closes the order and restores stock once. Other unclear states stay pending.
- The eSewa failure URL is not treated as final payment evidence. Unknown or non-complete eSewa status stays on hold for manual reconciliation.
- If payment initiation times out, the order is frozen for review. Do not retry the same order or clear the initiation guard based only on elapsed time.
- After a confirmed failure or cancellation, place a new order to start another payment. This version does not keep a payment-attempt ledger.
- Refunds, automated expiry/reconciliation, production payment operations, PostgreSQL concurrency behavior, and delivery fulfilment are outside this demo's verified scope.
- SQLite tests do not establish production concurrency guarantees. Use PostgreSQL transaction tests before relying on concurrent stock reservations.

## Academic materials

See [the report outline](docs/report.md), [architecture and state diagrams](docs/architecture.md), [test evidence](docs/test-evidence.md), and [demo script](docs/demo-script.md). Fill the institution-specific report fields and personal learning log yourself. Add real, redacted screenshots and actual sandbox evidence only after capturing them; do not invent payment evidence.
