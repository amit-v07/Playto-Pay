# Payout Engine Explainer

## 1. The Ledger

**Balance Calculation Query:**
```python
result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
    credits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.CREDIT)),
    debits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.DEBIT)),
)
balance = (result["credits"] or 0) - (result["debits"] or 0)
```

**Architectural Rationale:**
We use `BigIntegerField` to represent amounts in paise (the smallest currency unit) to strictly avoid floating-point arithmetic inaccuracies inherent in decimal systems. Instead of a mutable balance column that is susceptible to race conditions and "lost updates" during concurrent requests, we use an append-only, immutable ledger. This guarantees a mathematically provable, highly auditable source of truth where the balance is always a derived aggregation of all historical credits and debits.

## 2. The Lock

**Concurrency Control Snippet:**
```python
# Lock the merchant row — serialises concurrent balance checks
# for THIS merchant. Other merchants are unaffected.
merchant = Merchant.objects.select_for_update().get(id=merchant.id)
```

**Database Primitive:**
This relies on **PostgreSQL `FOR UPDATE` row-level locking**. By locking the merchant record before aggregating the ledger and checking the balance, we force any concurrent payout requests for the *same* merchant to queue up at the database level until the current transaction commits and releases the lock, completely preventing double-spend overdraws.

## 3. The Idempotency

**Key Recognition:**
The system queries the `IdempotencyKey` table using a composite unique constraint of `(merchant, key)`. If a row is found with a `DONE` status, it immediately bypasses processing and replays the cached `response_body` and `response_status_code`.

**Handling the "In-Flight" Race Condition:**
If two identical requests hit the API at the exact same millisecond, they could both see that the key doesn't exist and attempt to process the payout twice. We prevent this by issuing a lock on the key row:
```python
idem_key_obj = IdempotencyKey.objects.select_for_update(nowait=True).get(merchant=merchant, key=idempotency_key_value)
```
If the first request is still processing, it holds an exclusive lock on that row. When the second request executes the same query, the `nowait=True` directive causes PostgreSQL to immediately throw an `OperationalError` rather than waiting for the lock. The application catches this exception and returns an HTTP 409 Conflict. If the row doesn't exist yet, the first request atomically creates a sentinel row with an `IN_PROGRESS` status, locking out subsequent requests.

## 4. The State Machine

**State Transition Enforcement:**
```python
    LEGAL_TRANSITIONS: dict[str, set[str]] = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
        Status.COMPLETED: set(),   # terminal
        Status.FAILED: set(),      # terminal
    }

    def transition_to(
        self,
        new_status: str,
        actor: str = "system",
        metadata: dict | None = None,
    ) -> None:
        """
        Enforces the state machine and writes an immutable audit log entry.
        MUST be called within a transaction.atomic() block.
        """
        allowed = self.LEGAL_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidPayoutTransition(
                f"Cannot transition Payout {self.id} from {self.status!r} "
                f"to {new_status!r}. Allowed targets: {allowed or 'none (terminal state)'}."
            )
```
*Note: Because `Status.FAILED` maps to an empty set `set()`, any attempt to transition from `FAILED` to `COMPLETED` will immediately raise an `InvalidPayoutTransition` exception.*

## 5. The AI Audit

**Scenario 1: Reverse Relation ORM Bug**

*   **The Flaw:** During the generation of the `CreatePayoutView`, the AI produced a subtly incorrect Django ORM query when marking the idempotency key as `DONE`:
    ```python
    IdempotencyKey.objects.filter(id=idem_key_obj.id).update(
        status=IdempotencyKey.Status.DONE,
        payout=payout, # <-- THE BUG
    )
    ```
*   **How It Was Caught:** This code passed static analysis but crashed at runtime in the API container with an `AttributeError: 'OneToOneField' object has no attribute 'get_related_field'`.
*   **The Fix:** I identified that `payout` is a *reverse relation* on the `IdempotencyKey` model (the actual database column `idempotency_key_id` lives on the `Payout` table). Django's `.update()` method operates strictly on direct database columns and cannot be used to update reverse foreign keys. The fix was simply to remove `payout=payout` from the `.update()` call, as the relationship was already correctly established at the database level when the `Payout` object was instantiated.

**Scenario 2: Background Worker Queue Mismatch**

*   **The Flaw:** The AI generated a Celery worker startup command in `docker-compose.yml` with the flag `-Q default`. However, the Django application settings did not explicitly configure `CELERY_TASK_DEFAULT_QUEUE = "default"`.
*   **How It Was Caught:** During end-to-end testing, payouts successfully deducted from the ledger but remained permanently stuck in the `PENDING` state on the frontend dashboard. I inspected the Redis broker manually and found 31 tasks sitting completely unread in a list key named `celery`.
*   **The Fix:** I recognized that Celery's default queue name is `celery`, not `default`. Because the worker was isolated to listen only to the `default` queue via the `-Q` flag, it completely ignored the tasks Django was pushing to `celery`. The fix was to remove the `-Q default` flag from the worker command, allowing it to ingest the default queue natively. After a restart, the worker instantly processed the backlog of 31 stuck payouts.

**Scenario 3: Celery Task Race Condition**

*   **The Flaw:** When dispatching the asynchronous payout processing task to Celery, the AI generated a naive direct `.delay()` call:
    ```python
    with transaction.atomic():
        payout = Payout.objects.create(...)
        # ... other operations ...
        process_payout.delay(str(payout.id)) # <-- THE BUG
    ```
*   **How It Was Caught:** I immediately identified this as a classic Django/Celery race condition. If the Celery worker picks up the task from Redis *faster* than the PostgreSQL transaction commits on the API side, the worker will try to query the `Payout` object and crash with a `Payout.DoesNotExist` error.
*   **The Fix:** The AI attempted to fix this by merely un-indenting the `.delay()` call so it executed outside the `with transaction.atomic():` block. I rejected this as fragile, because if the view was ever wrapped in an overarching transaction (e.g., via `ATOMIC_REQUESTS=True` or during test suite execution), the race condition would return. I implemented the bulletproof fix using Django's built-in transaction hook to guarantee the task only dispatches *after* the outermost database transaction successfully commits:
    ```python
    transaction.on_commit(lambda: process_payout.delay(str(payout.id)))
    ```
