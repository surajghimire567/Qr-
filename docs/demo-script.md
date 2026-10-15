# Demo script (7–10 minutes)

Use a fresh demo database and synthetic customer data. Make clear which payment gateway and environment are being used. Save redacted screenshots or a screen recording as separate evidence; never stage a simulated callback as a live payment.

| Time | Demonstration | Explain |
| --- | --- | --- |
| 0:00–1:00 | Introduce Qr Shop, its users, scope, and architecture | This is an academic storefront. Payment integrations target sandbox/UAT. |
| 1:00–2:00 | Browse categories, open a product, show an unavailable product if available | Active status and stock control what a customer can buy. |
| 2:00–3:00 | Add/update a cart; show the empty-cart path | Guest carts use the session; signed-in carts use `SavedCart`. |
| 3:00–4:00 | Register or sign in; complete checkout | Checkout snapshots the unit price, checks stock, and reserves it within a transaction. |
| 4:00–5:00 | Open order detail as its owner; optionally try another account | Owner-filtered queries prevent another customer from viewing the address or order. |
| 5:00–6:30 | If a sandbox is configured, complete one payment and use the status return | Explain that only provider-side status and matching amount/reference can mark paid. Capture genuine evidence. |
| 6:30–7:30 | On a separate pending order, cancel before payment starts | Stock returns exactly once. An initiated or uncertain payment cannot be cancelled from the storefront. |
| 7:30–8:30 | Show order history pagination and read-only order admin | History is customer-scoped; the admin cannot type a paid status or edit item prices. |
| 8:30–10:00 | Show the test-evidence record and discuss limits | No refunds, automatic expiry reconciliation, or production concurrency claim is included. |

If a gateway is unavailable, show the pending/verification screen and state that a live sandbox payment was not completed. Do not use a prerecorded success as live evidence.

## Viva prompts to prepare independently

1. Why use `DecimalField`, and why keep a price on `OrderItem`?
2. Why does a browser `Completed` URL not prove payment?
3. What does the eSewa HMAC authenticate, and why perform a status lookup afterward?
4. How do `payment_ref` and `gateway_transaction_id` differ?
5. When is stock reserved or released? What happens on a timeout or duplicate callback?
6. What do CSRF, login checks, owner filters, password hashing, and read-only admin each protect?
7. Which concurrency guarantees do not follow from SQLite tests?
