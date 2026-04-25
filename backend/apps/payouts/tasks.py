import logging
import random
import time
from datetime import timedelta

import requests as http_requests
from celery import shared_task
from django.db import transaction, OperationalError
from django.utils import timezone

from apps.ledger.models import LedgerEntry
from apps.payouts.models import Payout, PayoutAuditLog

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
STUCK_THRESHOLD_SECONDS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fail_payout_and_return_funds(payout: Payout, reason: str, actor: str) -> None:
    """
    Atomically:
      1. Sets failure_reason on the payout.
      2. Inserts a CREDIT reversal LedgerEntry to return the held funds.
      3. Transitions the payout to FAILED.

    MUST be called inside an active transaction.atomic() block.
    The CREDIT entry is the only way funds are returned — no row is ever updated
    or deleted. Full audit trail is preserved.
    """
    payout.failure_reason = reason
    payout.save(update_fields=["failure_reason", "updated_at"])

    LedgerEntry.objects.create(
        merchant=payout.merchant,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=payout.amount,
        description=f"Reversal for failed payout {payout.id}",
        payout=payout,
    )

    payout.transition_to(
        Payout.Status.FAILED,
        actor=actor,
        metadata={"reason": reason, "reversal_created": True},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Bank settlement simulation
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=0, name="apps.payouts.tasks.process_payout")
def process_payout(self, payout_id: str) -> None:
    """
    Simulates a bank settlement.

    Worker idempotency guard:
      - SELECT FOR UPDATE NOWAIT on the Payout row WHERE status=PENDING.
      - If the row is not PENDING (crash + restart scenario), exit cleanly.
      - If another worker holds the lock, retry after 5s.

    Settlement outcome:
      - 80% chance of success (simulated).
      - On success: transition PROCESSING → COMPLETED.
      - On failure: transition PROCESSING → FAILED + atomic reversal CREDIT.
    """
    logger.info(f"[process_payout] Starting for payout_id={payout_id}")

    # ── Phase 1: Claim the payout (PENDING → PROCESSING) ──────────────────
    try:
        with transaction.atomic():
            try:
                payout = Payout.objects.select_for_update(nowait=True).get(
                    id=payout_id, status=Payout.Status.PENDING
                )
            except Payout.DoesNotExist:
                # Already transitioned by another worker or sweep — safe to skip.
                logger.info(
                    f"[process_payout] Payout {payout_id} not in PENDING state. "
                    "Skipping — idempotent exit."
                )
                return
            except OperationalError:
                # Lock contention — another worker is processing this payout.
                logger.warning(
                    f"[process_payout] Lock contention on payout {payout_id}. Retrying in 5s."
                )
                raise self.retry(countdown=5)

            payout.transition_to(
                Payout.Status.PROCESSING,
                actor="worker",
                metadata={"celery_task_id": self.request.id},
            )
            merchant = payout.merchant  # cache before leaving transaction
            amount = payout.amount

    except Exception as exc:
        logger.exception(f"[process_payout] Failed to claim payout {payout_id}: {exc}")
        raise

    # ── Phase 2: Simulate bank API call (outside transaction — no long locks) ─
    logger.info(f"[process_payout] Simulating bank call for {payout_id}…")
    time.sleep(random.uniform(0.5, 2.0))
    bank_success = random.random() > 0.2   # 80% success rate

    # ── Phase 3: Settle (PROCESSING → COMPLETED | FAILED) ─────────────────
    try:
        with transaction.atomic():
            # Re-fetch with lock — guard against concurrent sweep worker
            try:
                payout = Payout.objects.select_for_update(nowait=True).get(
                    id=payout_id, status=Payout.Status.PROCESSING
                )
            except Payout.DoesNotExist:
                logger.warning(
                    f"[process_payout] Payout {payout_id} no longer in PROCESSING. "
                    "Skipping settlement — idempotent exit."
                )
                return
            except OperationalError:
                logger.warning(
                    f"[process_payout] Lock contention during settlement of {payout_id}."
                )
                raise self.retry(countdown=5)

            if bank_success:
                bank_ref = f"BANK_REF_{str(payout_id).upper()[:8]}"
                payout.transition_to(
                    Payout.Status.COMPLETED,
                    actor="worker",
                    metadata={"bank_reference": bank_ref},
                )
                logger.info(f"[process_payout] Payout {payout_id} COMPLETED. ref={bank_ref}")
            else:
                _fail_payout_and_return_funds(
                    payout,
                    reason="Bank rejected the transfer.",
                    actor="worker",
                )
                logger.info(f"[process_payout] Payout {payout_id} FAILED — funds returned.")

    except Exception as exc:
        logger.exception(f"[process_payout] Settlement error for {payout_id}: {exc}")
        raise

    # ── Phase 4: Enqueue webhook (outside transaction) ─────────────────────
    deliver_webhook.delay(payout_id)


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Stuck payout sweep (runs every 30s via Celery Beat)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="apps.payouts.tasks.sweep_stuck_payouts")
def sweep_stuck_payouts() -> None:
    """
    Finds payouts stuck in PROCESSING for > 30 seconds and either:
      - Resets them to PENDING for retry (with exponential backoff), or
      - Fails them with a fund reversal if retry_count >= MAX_RETRIES.

    Uses select_for_update(skip_locked=True) so multiple beat instances don't
    double-process the same stuck payout.
    """
    threshold = timezone.now() - timedelta(seconds=STUCK_THRESHOLD_SECONDS)

    with transaction.atomic():
        stuck_payouts = list(
            Payout.objects.select_for_update(skip_locked=True).filter(
                status=Payout.Status.PROCESSING,
                processing_started_at__lt=threshold,
            )
        )

    if not stuck_payouts:
        return

    logger.info(f"[sweep_stuck_payouts] Found {len(stuck_payouts)} stuck payout(s).")

    for payout in stuck_payouts:
        with transaction.atomic():
            # Re-fetch inside individual transaction for safety
            try:
                payout = Payout.objects.select_for_update(nowait=True).get(
                    id=payout.id, status=Payout.Status.PROCESSING
                )
            except (Payout.DoesNotExist, OperationalError):
                continue  # Already handled by another process

            if payout.retry_count >= MAX_RETRIES:
                logger.warning(
                    f"[sweep] Payout {payout.id} exceeded max retries ({MAX_RETRIES}). Failing."
                )
                _fail_payout_and_return_funds(
                    payout,
                    reason=f"Exceeded maximum retry attempts ({MAX_RETRIES}).",
                    actor="sweep_worker",
                )
                deliver_webhook.delay(str(payout.id))

            else:
                backoff = min(2 ** payout.retry_count, 60)
                payout.retry_count += 1
                # Bypass transition_to() here because PROCESSING → PENDING is a
                # special recovery path only the sweep worker can invoke.
                payout.status = Payout.Status.PENDING
                payout.processing_started_at = None
                payout.save(
                    update_fields=[
                        "retry_count", "status", "processing_started_at", "updated_at"
                    ]
                )
                PayoutAuditLog.objects.create(
                    payout=payout,
                    actor="sweep_worker",
                    old_status=Payout.Status.PROCESSING,
                    new_status=Payout.Status.PENDING,
                    metadata={
                        "reason": "stuck_payout_recovery",
                        "retry_count": payout.retry_count,
                        "backoff_seconds": backoff,
                    },
                )
                process_payout.apply_async(args=[str(payout.id)], countdown=backoff)
                logger.info(
                    f"[sweep] Payout {payout.id} reset to PENDING — "
                    f"retry #{payout.retry_count}, backoff={backoff}s."
                )


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Webhook delivery
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=5,
    name="apps.payouts.tasks.deliver_webhook",
)
def deliver_webhook(self, payout_id: str) -> None:
    """
    Fires a webhook to merchant.webhook_url when a payout reaches a terminal state.
    Retries up to 5 times with exponential backoff on any request failure.
    """
    try:
        payout = Payout.objects.select_related("merchant").get(id=payout_id)
    except Payout.DoesNotExist:
        logger.error(f"[deliver_webhook] Payout {payout_id} not found.")
        return

    merchant = payout.merchant
    if not merchant.webhook_url:
        logger.info(f"[deliver_webhook] Merchant {merchant.id} has no webhook URL. Skipping.")
        return

    payload = {
        "event": "payout.updated",
        "payout_id": str(payout.id),
        "merchant_id": str(merchant.id),
        "status": payout.status,
        "amount_paise": payout.amount,
        "failure_reason": payout.failure_reason,
        "timestamp": timezone.now().isoformat(),
    }

    try:
        response = http_requests.post(
            merchant.webhook_url,
            json=payload,
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "X-Playtopay-Event": "payout.updated",
            },
        )
        response.raise_for_status()
        logger.info(
            f"[deliver_webhook] Delivered for payout {payout_id}. "
            f"HTTP {response.status_code}"
        )
    except http_requests.RequestException as exc:
        backoff = 2 ** self.request.retries
        logger.warning(
            f"[deliver_webhook] Failed for {payout_id}: {exc}. "
            f"Retry #{self.request.retries + 1} in {backoff}s."
        )
        raise self.retry(exc=exc, countdown=backoff)
