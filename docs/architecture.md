# Architecture and data model

## Data model

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    USER ||--o| SAVED_CART : owns
    CATEGORY ||--o{ PRODUCT : groups
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : snapshots
```

`SavedCart` belongs to an authenticated user. Guest cart lines live in the session, so a session cart is not a database table. Each `OrderItem` stores a unit-price snapshot. `Category` and products referenced by orders use protected deletion. The payment app has no payment-attempt table; each new order allows one claimed gateway attempt.

## Checkout and payment boundary

```mermaid
sequenceDiagram
    actor Customer
    participant Store as Django views
    participant DB as Database
    participant Gateway as Khalti or eSewa
    Customer->>Store: POST checkout with CSRF and checkout key
    Store->>DB: Lock products, create order/items, reserve stock
    DB-->>Store: Commit order with price snapshots
    Store-->>Customer: Owner-only pending order page
    Customer->>Store: POST start payment
    Store->>DB: Claim the one allowed payment start
    Store->>Gateway: Initiate payment
    Gateway-->>Customer: Provider payment page
    Gateway-->>Store: Browser return with provider reference
    Store->>Gateway: Server-side status lookup
    Gateway-->>Store: Provider status and receipt
    Store->>DB: Mark paid only after identity and amount checks
```

The browser return is a signal to check the provider. It is not evidence of payment by itself. The initiation ID stays in `payment_ref`; the final verified receipt is stored separately.

## Order lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: checkout reserves stock
    Pending --> Starting: one gateway claim
    Starting --> Pending: provider reference recorded
    Starting --> Starting: uncertain initiation; manual review
    Pending --> Paid: matching server-verified success
    Pending --> Cancelled: customer cancels before initiation
    Pending --> Failed: verified terminal Khalti non-payment
    Pending --> Pending: timeout, pending, unknown, eSewa failure return
    Cancelled --> [*]: stock released once
    Failed --> [*]: stock released once
    Paid --> [*]: no generic cancellation or restock
```

An eSewa `NOT_FOUND`, non-complete, contradictory, or unknown response remains pending for manual review. This is conservative: stock can remain reserved until an operator reconciles the provider. A late payment after stock release needs a separate refund/reconciliation workflow.

## Concurrency and operational limits

The service uses a database transaction, deterministic product ordering, conditional stock decrement, and row locks where supported. SQLite's `select_for_update()` does not establish the same concurrent transaction guarantees as PostgreSQL. Run concurrency tests on the intended production database before relying on simultaneous checkout behavior.
