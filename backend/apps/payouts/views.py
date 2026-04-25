import hashlib
import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction, OperationalError
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ledger.models import LedgerEntry
from apps.merchants.models import Merchant
from apps.payouts.models import IdempotencyKey, Payout, PayoutAuditLog
from apps.payouts.serializers import (
    CreatePayoutSerializer,
    PayoutDetailSerializer,
    PayoutSerializer,
)
from apps.payouts.tasks import process_payout

logger = logging.getLogger(__name__)


class CreatePayoutView(APIView):
    """
    POST /api/v1/payouts/

    Requires header:  Idempotency-Key: <UUID v4>

    Critical section protocol:
      1. SELECT idempotency_key FOR UPDATE NOWAIT
         → IN_PROGRESS: return 409 (in-flight duplicate)
         → DONE:        return cached response (idempotent replay)
         → NOT FOUND:   INSERT sentinel with status=IN_PROGRESS

      2. SELECT merchant FOR UPDATE (blocking)
         → serialises ALL concurrent balance checks for this merchant
         → prevents double-spend

      3. Compute balance via DB aggregation inside the locked transaction
      4. If balance >= amount: INSERT LedgerEntry(DEBIT) + Payout(PENDING)
      5. COMMIT → enqueue Celery task
      6. UPDATE idempotency_key → status=DONE, cache response
    """

    def post(self, request):
        merchant: Merchant = request.user.merchant

        # ── 1. Validate Idempotency-Key header ─────────────────────────────
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            return Response(
                {"error": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            idempotency_key_value = uuid.UUID(raw_key)
        except (ValueError, AttributeError):
            return Response(
                {"error": "Idempotency-Key must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 2. Validate request body ────────────────────────────────────────
        serializer = CreatePayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount: int = serializer.validated_data["amount"]

        request_hash = hashlib.sha256(
            json.dumps(request.data, sort_keys=True).encode()
        ).hexdigest()

        # ── 3. Idempotency check — in-flight race protected ─────────────────
        idem_key_obj = None
        try:
            with transaction.atomic():
                try:
                    idem_key_obj = IdempotencyKey.objects.select_for_update(
                        nowait=True
                    ).get(merchant=merchant, key=idempotency_key_value)

                    # Handle expired key — treat as new request
                    if idem_key_obj.is_expired():
                        idem_key_obj.delete()
                        idem_key_obj = None
                    elif idem_key_obj.status == IdempotencyKey.Status.IN_PROGRESS:
                        return Response(
                            {
                                "error": "A request with this Idempotency-Key is already being processed.",
                                "idempotency_key": str(idempotency_key_value),
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    elif idem_key_obj.status == IdempotencyKey.Status.DONE:
                        # Replay exact cached response
                        logger.info(
                            f"[CreatePayoutView] Idempotent replay for key {idempotency_key_value}"
                        )
                        return Response(
                            idem_key_obj.response_body,
                            status=idem_key_obj.response_status_code,
                            headers={"X-Idempotency-Replayed": "true"},
                        )

                except IdempotencyKey.DoesNotExist:
                    idem_key_obj = None

                except OperationalError:
                    # Lock contention — another request is holding this key
                    return Response(
                        {
                            "error": "A request with this Idempotency-Key is already being processed.",
                            "idempotency_key": str(idempotency_key_value),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                if idem_key_obj is None:
                    # Insert IN_PROGRESS sentinel atomically
                    idem_key_obj = IdempotencyKey.objects.create(
                        merchant=merchant,
                        key=idempotency_key_value,
                        status=IdempotencyKey.Status.IN_PROGRESS,
                        request_hash=request_hash,
                        expires_at=timezone.now()
                        + timedelta(hours=settings.IDEMPOTENCY_KEY_EXPIRY_HOURS),
                    )

        except Exception as exc:
            logger.exception(f"[CreatePayoutView] Idempotency check error: {exc}")
            return Response(
                {"error": "Internal server error during idempotency check."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ── 4. Balance check + debit — the critical section ─────────────────
        try:
            with transaction.atomic():
                # Lock the merchant row — serialises concurrent balance checks
                # for THIS merchant. Other merchants are unaffected.
                merchant = Merchant.objects.select_for_update().get(id=merchant.id)

                # Compute balance from DB aggregation inside the locked snapshot
                result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
                    credits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.CREDIT)),
                    debits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.DEBIT)),
                )
                balance = (result["credits"] or 0) - (result["debits"] or 0)

                if balance < amount:
                    # Mark idempotency key as DONE with the 402 error response
                    error_body = {
                        "error": "Insufficient balance.",
                        "balance_paise": balance,
                        "requested_paise": amount,
                    }
                    IdempotencyKey.objects.filter(id=idem_key_obj.id).update(
                        status=IdempotencyKey.Status.DONE,
                        response_status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        response_body=error_body,
                    )
                    return Response(error_body, status=status.HTTP_402_PAYMENT_REQUIRED)

                # Create the DEBIT entry (immutable ledger)
                debit_entry = LedgerEntry.objects.create(
                    merchant=merchant,
                    entry_type=LedgerEntry.EntryType.DEBIT,
                    amount=amount,
                    description=f"Payout request for ₹{amount / 100:.2f}",
                )

                # Create Payout in PENDING state
                payout = Payout.objects.create(
                    merchant=merchant,
                    amount=amount,
                    status=Payout.Status.PENDING,
                    idempotency_key=idem_key_obj,
                )

                # Link debit entry to payout
                # (Direct update safe here since it's a new row in same tx)
                LedgerEntry.objects.filter(id=debit_entry.id).update(payout=payout)

                # Write initial audit log entry
                PayoutAuditLog.objects.create(
                    payout=payout,
                    actor=f"merchant:{merchant.id}",
                    old_status=None,
                    new_status=Payout.Status.PENDING,
                    metadata={"amount_paise": amount, "idempotency_key": str(idempotency_key_value)},
                )

                # ── 5. Enqueue settlement task (post-commit hook) ────────────
                transaction.on_commit(lambda: process_payout.delay(str(payout.id)))
                
            logger.info(
                f"[CreatePayoutView] Payout {payout.id} created and enqueued. "
                f"Amount={amount} paise, merchant={merchant.id}"
            )

            # ── 6. Build response and mark idempotency key DONE ────────────
            response_body = PayoutSerializer(payout).data
            response_status = status.HTTP_201_CREATED
            IdempotencyKey.objects.filter(id=idem_key_obj.id).update(
                status=IdempotencyKey.Status.DONE,
                response_status_code=response_status,
                response_body=response_body,
            )

            return Response(response_body, status=response_status)

        except Exception as exc:
            # Mark idempotency key as DONE with 500 to prevent retries from
            # getting stuck — caller should use a new key on retry.
            logger.exception(f"[CreatePayoutView] Unexpected error: {exc}")
            try:
                IdempotencyKey.objects.filter(id=idem_key_obj.id).update(
                    status=IdempotencyKey.Status.DONE,
                    response_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    response_body={"error": "Internal server error. Use a new Idempotency-Key to retry."},
                )
            except Exception:
                pass
            return Response(
                {"error": "Internal server error. Use a new Idempotency-Key to retry."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PayoutListView(ListAPIView):
    serializer_class = PayoutSerializer

    def get_queryset(self):
        merchant: Merchant = self.request.user.merchant
        qs = Payout.objects.filter(merchant=merchant)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        return qs


class PayoutDetailView(RetrieveAPIView):
    serializer_class = PayoutDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Payout.objects.filter(
            merchant=self.request.user.merchant
        ).prefetch_related("audit_logs")
