# Payout Engine — Architectural Implementation Plan

## Overview

A production-grade, money-moving system for merchant payouts built on Django + PostgreSQL + Celery.  
The design centres on **four non-negotiable pillars**: financial correctness (immutable ledger), concurrency safety (DB-level row locks), idempotency (request *and* worker level), and an auditable strict state machine.

---

## User Review Required

> [!IMPORTANT]
> All monetary values are stored as **paise** (`BigIntegerField`). The API layer accepts and returns paise as well. No float conversion happens at any layer.

> [!WARNING]
> `select_for_update(nowait=False)` is used inside atomic transactions. This means concurrent requests **will block** (not 409 immediately) until the lock holder commits. If you prefer a `nowait=True` behaviour (immediate 409 on contention), call that out and I'll swap strategies.

> [!CAUTION]
> The idempotency key table uses a `PENDING` sentinel state written *before* the actual work begins. This is the correct pattern to handle in-flight race conditions, but it means the second concurrent request will receive an HTTP 409 "Request In Progress" until the first one settles. This is industry-standard behaviour (Stripe, Razorpay). Confirm if that's acceptable.

---

## Open Questions

1. **Multi-currency?** — Plan assumes single currency (INR/paise). If multi-currency is needed later, `LedgerEntry.currency` and `Payout.currency` fields should be added now.
2. **Merchant auth?** — Plan uses Django's built-in `User` model linked 1-to-1 to `Merchant`. Should JWT (SimpleJWT) or session auth be used?  
3. **Webhook URL** — Is the dummy merchant webhook URL configurable per merchant (stored in `Merchant.webhook_url`) or a global env var for now?
4. **Frontend scope** — React + Tailwind frontend is listed as a bonus. Should it be scaffolded in the same repo (`frontend/`) or as a separate service? Lean toward monorepo.

---

## Database Schema Design

### Entity Relationship Overview

```
User (Django built-in)
 └─── Merchant (1-to-1)
        ├─── LedgerEntry (many)   ← immutable, append-only credits & debits
        ├─── Payout (many)        ← one payout per withdrawal request
        │      └─── PayoutAuditLog (many)
        └─── IdempotencyKey (many)
```

---

### 1. `Merchant` model

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user` | OneToOneField(User) | Django auth user |
| `business_name` | CharField | |
| `webhook_url` | URLField, nullable | target for payout webhooks |
| `created_at` | DateTimeField(auto_now_add) | UTC enforced via `USE_TZ=True` |

**Balance is never stored here.** It is always computed as:
```sql
SELECT COALESCE(SUM(amount) FILTER (WHERE entry_type='CREDIT'), 0)
     - COALESCE(SUM(amount) FILTER (WHERE entry_type='DEBIT'), 0)
  FROM ledger_entry
 WHERE merchant_id = <id>;
```

---

### 2. `LedgerEntry` model — The Source of Truth

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `merchant` | ForeignKey(Merchant) | |
| `entry_type` | CharField choices: `CREDIT`, `DEBIT` | |
| `amount` | BigIntegerField | Always positive, in paise |
| `description` | CharField | e.g. "Payment received", "Payout #xyz" |
| `payout` | ForeignKey(Payout, null=True) | Links debit rows back to the payout |
| `created_at` | DateTimeField(auto_now_add) | UTC |

**Rules:**
- **Append-only.** No `update()` or `delete()` is ever called on this table.
- A `DEBIT` entry is created *atomically inside the same transaction* that creates a `Payout` record.
- If the payout fails, a corresponding `CREDIT` reversal entry is inserted (not a row update) to return funds — this preserves full audit history.

---

### 3. `Payout` model — State Machine

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `merchant` | ForeignKey(Merchant) | |
| `amount` | BigIntegerField | In paise |
| `status` | CharField choices | See state machine below |
| `idempotency_key` | ForeignKey(IdempotencyKey) | |
| `failure_reason` | TextField, null | Populated on failure |
| `retry_count` | PositiveSmallIntegerField default=0 | For stuck-payout sweep |
| `processing_started_at` | DateTimeField, null | Set when entering `PROCESSING` |
| `created_at` | DateTimeField(auto_now_add) | UTC |
| `updated_at` | DateTimeField(auto_now) | UTC |

#### State Machine & Legal Transitions

```
                   ┌─────────────────────────────────┐
                   │           PENDING                │  ← created here
                   └────────────┬────────────────────-┘
                                │  worker picks up
                                ▼
                   ┌─────────────────────────────────┐
                   │          PROCESSING              │
                   └────────┬────────────┬────────────┘
               success      │            │  failure / max retries
                            ▼            ▼
                   ┌──────────────┐  ┌──────────────────────┐
                   │  COMPLETED   │  │       FAILED         │
                   └──────────────┘  └──────────────────────┘
                   (terminal)         (terminal — funds returned)
```

**Illegal transitions** enforced by a model-level `clean()` / `save()` override *and* a DB constraint via `CheckConstraint`:

| From | To | Allowed? |
|---|---|---|
| `PENDING` | `PROCESSING` | ✅ |
| `PROCESSING` | `COMPLETED` | ✅ |
| `PROCESSING` | `FAILED` | ✅ |
| `COMPLETED` | any | ❌ raises `InvalidTransition` |
| `FAILED` | any | ❌ raises `InvalidTransition` |
| `PENDING` | `COMPLETED`/`FAILED` | ❌ (must pass through PROCESSING) |

---

### 4. `IdempotencyKey` model

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `merchant` | ForeignKey(Merchant) | Scoped per merchant |
| `key` | UUIDField | The key from the header |
| `status` | CharField choices: `IN_PROGRESS`, `DONE` | |
| `request_hash` | CharField | SHA-256 of request body (optional integrity check) |
| `response_status_code` | PositiveSmallIntegerField, null | Cached HTTP status |
| `response_body` | JSONField, null | Cached response payload |
| `payout` | OneToOneField(Payout, null=True) | Set when DONE |
| `expires_at` | DateTimeField | `created_at + 24h` |
| `created_at` | DateTimeField(auto_now_add) | UTC |

**Unique constraint:** `(merchant, key)` — prevents cross-merchant key collisions.

#### In-Flight Race Condition Protocol

This is the trickiest part. The flow is:

```
Request arrives with Idempotency-Key X:
  1. BEGIN TRANSACTION
  2. SELECT ... FROM idempotency_key WHERE merchant=M AND key=X FOR UPDATE NOWAIT
     - If row not found → INSERT with status=IN_PROGRESS → COMMIT → proceed with work
     - If found AND status=DONE   → COMMIT → return cached response (HTTP 200/201)
     - If found AND status=IN_PROGRESS → COMMIT → return HTTP 409 "Request In Progress"
  3. Do the actual work (balance check, debit, create Payout)
  4. BEGIN TRANSACTION
  5. UPDATE idempotency_key SET status=DONE, response_body=..., response_status_code=...
  6. COMMIT
```

`FOR UPDATE NOWAIT` on step 2 means if two requests race to insert the same key, only one wins the lock. The other gets a `OperationalError` which we catch and translate to HTTP 409.

---

### 5. `PayoutAuditLog` model — Immutable Event Log

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `payout` | ForeignKey(Payout) | |
| `actor` | CharField | `"system"`, `"merchant:<id>"`, `"worker"` |
| `old_status` | CharField, null | null for creation event |
| `new_status` | CharField | |
| `metadata` | JSONField default=dict | arbitrary context (e.g. failure reason) |
| `created_at` | DateTimeField(auto_now_add) | UTC |

Rules:
- **Never updated or deleted.** Only `INSERT`.
- Written inside the same atomic transaction as the state change.

---

## Where Locks Are Applied

| Operation | Lock Type | Scope | Reason |
|---|---|---|---|
| Idempotency key lookup | `SELECT … FOR UPDATE NOWAIT` | `IdempotencyKey` row | Prevent in-flight duplicate processing |
| Balance check & debit | `SELECT … FOR UPDATE` | `Merchant` row | Prevent double-spend race condition |
| Payout status transition | `SELECT … FOR UPDATE` | `Payout` row | Worker idempotency — prevent double settlement |

The `Merchant` row lock during balance check is the **critical section**. The full sequence inside `@transaction.atomic`:

```
1. merchant = Merchant.objects.select_for_update().get(id=merchant_id)
2. balance = LedgerEntry.objects.filter(merchant=merchant).aggregate(...)  # computed from locked snapshot
3. if balance < requested_amount → raise InsufficientFunds → rollback
4. INSERT LedgerEntry(type=DEBIT, amount=requested_amount)
5. INSERT Payout(status=PENDING)
6. INSERT PayoutAuditLog(old=None, new=PENDING)
7. COMMIT
```

Because the `Merchant` row is locked from step 1 until commit, any concurrent request for the **same merchant** will block at step 1 until this transaction completes. This guarantees serialised balance checks per merchant.

---

## Background Workers (Celery)

### Task 1: `process_payout` — Bank Settlement Simulation

```
1. SELECT payout WHERE id=<id> AND status=PENDING FOR UPDATE NOWAIT
   - If not found or status ≠ PENDING → task is a duplicate, exit idempotently
2. UPDATE payout SET status=PROCESSING, processing_started_at=now()
3. INSERT PayoutAuditLog(PENDING → PROCESSING)
4. COMMIT
5. Simulate bank API call (sleep + random success/failure)
6. BEGIN TRANSACTION
   - If success:
       UPDATE payout SET status=COMPLETED
       INSERT PayoutAuditLog(PROCESSING → COMPLETED)
   - If failure:
       UPDATE payout SET status=FAILED, failure_reason=...
       INSERT LedgerEntry(type=CREDIT, amount=held_amount)  ← atomic reversal
       INSERT PayoutAuditLog(PROCESSING → FAILED)
7. COMMIT
8. Enqueue `deliver_webhook` task
```

**Worker idempotency:** The `FOR UPDATE NOWAIT` + `status=PENDING` guard in step 1 means if the worker crashes after step 4 and restarts, it will find `status=PROCESSING` and exit without double-settling. The stuck-payout sweep handles recovery.

### Task 2: `sweep_stuck_payouts` — Periodic Recovery (every 30s)

```
1. Find payouts WHERE status=PROCESSING AND processing_started_at < now()-30s AND retry_count < 3
2. For each stuck payout (with SELECT FOR UPDATE NOWAIT on each row):
   a. retry_count += 1
   b. Calculate backoff delay: min(2^retry_count, 60) seconds
   c. Re-enqueue `process_payout` with countdown=backoff_delay
   d. Reset status to PENDING (so `process_payout` guard in step 1 allows re-entry)
   e. INSERT PayoutAuditLog (PROCESSING → PENDING, metadata={retry: n, reason: "stuck"})
3. Find payouts WHERE status=PROCESSING AND retry_count >= 3
   a. Transition to FAILED atomically
   b. INSERT reversal LedgerEntry(CREDIT)
   c. INSERT PayoutAuditLog(PROCESSING → FAILED, metadata={reason: "max_retries_exceeded"})
   d. Enqueue `deliver_webhook`
```

### Task 3: `deliver_webhook` — Webhook Delivery

```
Celery task with autoretry_for=(RequestException,) max_retries=5 exponential backoff
1. POST to merchant.webhook_url with payload:
   { payout_id, status, amount, timestamp }
2. On non-2xx response → raise exception → Celery retries with backoff
3. On max retries exhausted → log failure, mark webhook as undeliverable
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/token/` | JWT login |
| `POST` | `/api/v1/ledger/credit/` | Simulate incoming payment (credit merchant) |
| `GET` | `/api/v1/ledger/balance/` | Get merchant balance (DB aggregation) |
| `GET` | `/api/v1/ledger/transactions/` | List ledger entries (paginated) |
| `POST` | `/api/v1/payouts/` | Request a payout (idempotency-key required) |
| `GET` | `/api/v1/payouts/` | List payouts |
| `GET` | `/api/v1/payouts/{id}/` | Get payout detail + audit log |

---

## Project Structure

```
playtopay/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py
│   └── apps/
│       ├── merchants/       # Merchant model, auth
│       ├── ledger/          # LedgerEntry, balance views
│       └── payouts/         # Payout, IdempotencyKey, AuditLog, tasks
├── frontend/
│   ├── package.json
│   └── src/
└── nginx/
    └── nginx.conf
```

---

## Verification Plan

### Automated Tests
- `pytest` with `pytest-django` and `factory_boy`
- **Concurrency test:** spawn 10 threads simultaneously submitting withdrawals for the same merchant with insufficient balance for all — assert only one succeeds
- **Idempotency test:** POST same request with same key twice — assert identical response, single `Payout` row
- **In-flight test:** mock the first request mid-execution, send second with same key — assert HTTP 409
- **State machine test:** attempt all illegal transitions — assert `InvalidTransition` raised
- **Atomic failure test:** inject failure inside worker transaction — assert no half-written rows, funds returned

### Manual / Docker Verification
- `docker compose up --build` → all 5 services healthy
- POST credits → check balance endpoint returns correct paise sum
- POST payout → Celery picks up → status transitions visible in GET detail
- Kill worker mid-payout → sweep task recovers it after 30s
- Check audit log has full immutable history
