"""
Critical tests for financial integrity, idempotency, concurrency, and state machine.
"""
import threading
import uuid

import pytest
from django.db import transaction
from django.urls import reverse

from apps.ledger.models import LedgerEntry
from apps.payouts.models import Payout, IdempotencyKey, InvalidPayoutTransition


# ─────────────────────────────────────────────────────────────────────────────
# Balance & Ledger tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_balance_is_computed_from_ledger(merchant):
    """Balance must always be derived from ledger aggregation."""
    assert merchant.get_balance() == 1_000_000

    LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=500_000,
        description="Extra credit",
    )
    assert merchant.get_balance() == 1_500_000


@pytest.mark.django_db
def test_ledger_entry_is_immutable(merchant):
    """LedgerEntry must not be updatable or deletable."""
    entry = LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=100_00,
        description="Test",
    )
    with pytest.raises(PermissionError):
        entry.description = "Mutated"
        entry.save()

    with pytest.raises(PermissionError):
        entry.delete()


@pytest.mark.django_db
def test_ledger_amount_must_be_positive(merchant):
    with pytest.raises((ValueError, Exception)):
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# State machine tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_legal_payout_transitions(merchant):
    payout = Payout.objects.create(merchant=merchant, amount=100_00)
    payout.transition_to(Payout.Status.PROCESSING, actor="test")
    assert payout.status == Payout.Status.PROCESSING

    payout.transition_to(Payout.Status.COMPLETED, actor="test")
    assert payout.status == Payout.Status.COMPLETED


@pytest.mark.django_db
def test_illegal_transition_completed_to_pending(merchant):
    payout = Payout.objects.create(merchant=merchant, amount=100_00, status=Payout.Status.COMPLETED)
    with pytest.raises(InvalidPayoutTransition):
        payout.transition_to(Payout.Status.PENDING, actor="test")


@pytest.mark.django_db
def test_illegal_transition_failed_to_completed(merchant):
    payout = Payout.objects.create(merchant=merchant, amount=100_00, status=Payout.Status.FAILED)
    with pytest.raises(InvalidPayoutTransition):
        payout.transition_to(Payout.Status.COMPLETED, actor="test")


@pytest.mark.django_db
def test_illegal_transition_pending_to_completed(merchant):
    """Must pass through PROCESSING — cannot skip states."""
    payout = Payout.objects.create(merchant=merchant, amount=100_00)
    with pytest.raises(InvalidPayoutTransition):
        payout.transition_to(Payout.Status.COMPLETED, actor="test")


# ─────────────────────────────────────────────────────────────────────────────
# API: Idempotency tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_idempotent_payout_returns_same_response(auth_client):
    """Same Idempotency-Key must return the exact same response and single Payout."""
    idem_key = str(uuid.uuid4())
    payload = {"amount": 100_00}

    r1 = auth_client.post(
        "/api/v1/payouts/",
        data=payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=idem_key,
    )
    assert r1.status_code == 201

    r2 = auth_client.post(
        "/api/v1/payouts/",
        data=payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=idem_key,
    )
    assert r2.status_code == 201
    assert r1.data["id"] == r2.data["id"]
    assert r2.headers.get("X-Idempotency-Replayed") == "true"

    # Only ONE payout must exist
    assert Payout.objects.filter(merchant=auth_client.merchant).count() == 1


@pytest.mark.django_db(transaction=True)
def test_insufficient_balance_returns_402(auth_client):
    """Payout exceeding balance must return 402."""
    idem_key = str(uuid.uuid4())
    r = auth_client.post(
        "/api/v1/payouts/",
        data={"amount": 999_999_999},  # Way more than the ₹10,000 balance
        format="json",
        HTTP_IDEMPOTENCY_KEY=idem_key,
    )
    assert r.status_code == 402
    assert "balance_paise" in r.data


@pytest.mark.django_db(transaction=True)
def test_missing_idempotency_key_returns_400(auth_client):
    r = auth_client.post("/api/v1/payouts/", data={"amount": 100_00}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_invalid_idempotency_key_format_returns_400(auth_client):
    r = auth_client.post(
        "/api/v1/payouts/",
        data={"amount": 100_00},
        format="json",
        HTTP_IDEMPOTENCY_KEY="not-a-uuid",
    )
    assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Concurrency: double-spend prevention
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_concurrent_payouts_cannot_double_spend(make_merchant):
    """
    10 concurrent threads each attempt to withdraw the full balance.
    Only ONE should succeed; the rest should get 402.
    """
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    merchant = make_merchant(username="concurrent_test", balance_paise=100_00)

    results = []
    errors = []

    def attempt_payout():
        client = APIClient()
        refresh = RefreshToken.for_user(merchant.user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        try:
            r = client.post(
                "/api/v1/payouts/",
                data={"amount": 100_00},
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            )
            results.append(r.status_code)
        except Exception as e:
            errors.append(str(e))
        finally:
            from django.db import connection
            connection.close()

    threads = [threading.Thread(target=attempt_payout) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors: {errors}"
    successes = results.count(201)
    failures = results.count(402)

    # Exactly one payout can succeed — balance is 100_00 paise
    assert successes == 1, f"Expected 1 success, got {successes}. Results: {results}"
    assert failures == 9, f"Expected 9 failures (402), got {failures}. Results: {results}"

    # Verify ledger integrity: balance should be 0
    assert merchant.get_balance() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Failure atomicity: failed payout must return funds
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_failed_payout_returns_funds_atomically(merchant):
    """A FAILED payout must create an exact reversal CREDIT entry."""
    initial_balance = merchant.get_balance()
    payout_amount = 50_000

    with transaction.atomic():
        # Simulate: create debit + payout
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount=payout_amount,
            description="Test debit",
        )
        payout = Payout.objects.create(
            merchant=merchant,
            amount=payout_amount,
            status=Payout.Status.PROCESSING,
        )
        payout.processing_started_at = payout.created_at
        payout.save(update_fields=["processing_started_at", "updated_at"])

        # Simulate failure + reversal
        from apps.payouts.tasks import _fail_payout_and_return_funds
        _fail_payout_and_return_funds(payout, reason="Test failure", actor="test")

    # Balance must be fully restored
    assert merchant.get_balance() == initial_balance

    # Verify a CREDIT reversal exists
    reversal = LedgerEntry.objects.filter(
        merchant=merchant,
        entry_type=LedgerEntry.EntryType.CREDIT,
        payout=payout,
    ).first()
    assert reversal is not None
    assert reversal.amount == payout_amount

    # Verify payout is FAILED
    payout.refresh_from_db()
    assert payout.status == Payout.Status.FAILED

    # Verify audit log recorded the transition
    from apps.payouts.models import PayoutAuditLog
    log = PayoutAuditLog.objects.filter(payout=payout, new_status=Payout.Status.FAILED).first()
    assert log is not None
    assert log.metadata.get("reversal_created") is True
