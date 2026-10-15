# Academic project report outline

Use the institution's required report template, section order, and citation style before submitting.

## Front matter

- **Project title:** [Enter approved title]
- **Student name and ID:** [Enter your own details]
- **Supervisor:** [Enter approved details]
- **Institution and department:** [Enter official names]
- **Declaration / approvals:** [Use the institution's required wording and signatures; do not invent approvals]

## Abstract and problem

Describe the local problem, intended users, project objective, implemented scope, technology stack, verification method, actual results, and limitations. Write the final abstract after the test-evidence record is complete. State that the payment adapters target provider sandbox/UAT environments and that no live transaction is implied.

## Requirements and traceability

| Requirement | Implementation | Evidence to cite |
| --- | --- | --- |
| Browse products by category and inspect stock | `store` app and templates | Catalog and view tests; redacted browser capture |
| Maintain guest and account carts | Session cart and `SavedCart` | Cart tests; account-cart demo |
| Create an order with historical prices | `orders.services.create_order_from_cart` | Checkout and snapshot tests |
| Restrict order access to its owner | owner-filtered order/payment views | Ownership tests |
| Verify a sandbox payment | `payments` gateway/service boundary | Mock regression tests plus separately captured real sandbox evidence, if performed |
| Cancel before initiation and restore stock once | `orders.services.release_unpaid` | Stock lifecycle tests |
| Review orders without editing financial state | Django order admin | Admin tests or reviewed admin capture |

Add nonfunctional requirements such as access control, transaction correctness, usability, and maintainability, each linked to actual evidence.

## Design and implementation

Use [the data model and state diagrams](architecture.md). Explain Decimal money, order-item price snapshots, atomic checkout, CSRF-protected POST actions, owner-filtered queries, eSewa HMAC verification, and the independent server-side gateway lookup. Include short relevant extracts only; do not paste a source dump.

## Testing and results

Copy the environment, commands, actual pass/fail counts, failures and fixes from [the test-evidence record](test-evidence.md). Clearly separate automated mock tests from manual browser work and actual provider sandbox transactions. Do not describe a mock as a real payment.

## Conclusion and limitations

Summarize what was implemented and measured. Discuss pending-stock reconciliation, no refunds or payment-attempt ledger, no verified production deployment, and SQLite concurrency limits. Describe future work such as audited payment attempts, expiry monitoring, refunds, and production operations.

## References and disclosure

- [Django documentation](https://docs.djangoproject.com/)
- [Khalti ePayment documentation](https://docs.khalti.com/khalti-epayment/)
- [eSewa ePay v2 documentation](https://developer.esewa.com.np/pages/Epay-V2)
- [eSewa ePay documentation](https://developer.esewa.com.np/pages/Epay)
- [Project repository origin](https://github.com/surajghimire567/Qr-)

Disclose AI-assisted code review and drafting according to the institution's rules. Review and explain every change yourself. Verify permission and attribution for any third-party product images used in a submission.
