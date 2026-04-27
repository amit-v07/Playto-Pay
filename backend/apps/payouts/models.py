import uuid
from django.db import models
from django.utils import timezone
from apps.merchants.models import Merchant


class InvalidPayoutTransition(Exception):
    """Raised when an illegal Payout state transition is attempted."""
    pass


class IdempotencyKey(models.Model):
    """
    Per-merchant idempotency key store.

    Flow:
      1. First request: INSERT with status=IN_PROGRESS (sentinel).
      2. Work completes: UPDATE to status=DONE, cache response_body.
      3. Duplicate request while IN_PROGRESS: return HTTP 409.
      4. Duplicate request when DONE: return cached response.
      5. Expired keys (>24h): treated as new.
    """

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        DONE = "DONE", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name="idempotency_keys"
    )
    key = models.UUIDField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )
    request_hash = models.CharField(max_length=64, blank=True)
    response_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_keys"
        # Scoped per merchant — same key for different merchants is allowed
        unique_together = [("merchant", "key")]
        indexes = [
            models.Index(fields=["merchant", "key"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"IdempotencyKey {self.key} [{self.status}]"


class Payout(models.Model):
    """
    Represents one merchant withdrawal request.

    State machine (enforced by transition_to()):
        PENDING → PROCESSING → COMPLETED  (terminal)
                             → FAILED     (terminal, funds returned)

    All transitions are validated before save and audit-logged atomically.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    LEGAL_TRANSITIONS: dict[str, set[str]] = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
        Status.COMPLETED: set(),   # terminal
        Status.FAILED: set(),      # terminal
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="payouts"
    )
    amount = models.BigIntegerField()   # paise, always positive
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    idempotency_key = models.OneToOneField(
        IdempotencyKey,
        on_delete=models.PROTECT,
        related_name="payout",
        null=True,
        blank=True,
    )
    failure_reason = models.TextField(blank=True, null=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payouts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["status", "processing_started_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="payout_amount_must_be_positive",
            ),
        ]

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

        old_status = self.status
        self.status = new_status
        if new_status == self.Status.PROCESSING:
            self.processing_started_at = timezone.now()

        self.save(update_fields=["status", "processing_started_at", "updated_at"])

        PayoutAuditLog.objects.create(
            payout=self,
            actor=actor,
            old_status=old_status,
            new_status=new_status,
            metadata=metadata or {},
        )

    def __str__(self):
        return f"Payout {self.id} [{self.status}] {self.amount} paise"


class PayoutAuditLog(models.Model):
    """
    Immutable event log for every Payout state transition.
    Written atomically inside the same transaction as the state change.
    Never updated, never deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout = models.ForeignKey(
        Payout, on_delete=models.PROTECT, related_name="audit_logs"
    )
    actor = models.CharField(max_length=100)   # "system", "merchant:<id>", "worker"
    old_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payout_audit_logs"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if self.pk and PayoutAuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("PayoutAuditLog is immutable — updates are forbidden.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("PayoutAuditLog is immutable — deletion is forbidden.")

    def __str__(self):
        return f"AuditLog [{self.payout_id}] {self.old_status} → {self.new_status}"
