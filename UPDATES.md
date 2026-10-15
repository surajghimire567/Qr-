# Project updates

## Day 6 completion work — 15 October 2026

- Added `cart/__init__.py` so Django's default test discovery includes the cart app.
- Kept the existing account/profile/history routes and completed the ten-orders-per-page history UI.
- Added checkout idempotency keys, conditional stock decrement, nonnegative money constraints, and an exactly-once unpaid-stock release service.
- Added a cancellation endpoint that is POST-only and only works before payment initiation.
- Separated provider initiation references from final payment receipts. Payment initiation is claimed once per order, and paid-state transitions require matching provider/reference data and server-side verification.
- Changed eSewa failure redirects and uncertain provider responses to remain pending. Added a POST-only owner status check.
- Hardened gateway JSON, callback signatures, provider identity, amounts, and response-shape handling. Payment tests use mocks only.
- Made order and order-item admin records read-only, while preserving catalog administration.
- Added a reproducible synthetic demo catalog command, updated environment examples, refreshed setup and lifecycle documentation, and added architecture, report, evidence, and demo materials.
- Removed the inspected placeholder files `abc`, `cart/templates/cart/abc`, `store/templates/aaa`, and `store/a/templates/zzz`.

## Verification record

See [docs/test-evidence.md](docs/test-evidence.md) for the actual commands and results recorded for this workspace. Sandbox transactions, a hosted deployment, and browser screenshots have not been fabricated or represented as verified evidence.
