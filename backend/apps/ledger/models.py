import uuid
from django.db import models
from apps.merchants.models import Merchant


class LedgerEntry(models.Model):
    """
    Immutable, append-only financial ledger.

    Rules enforced:
    - amount is ALWAYS a positive BigInteger in paise.
    - Once created, rows can NEVER be updated or deleted.
    - Balance is NEVER stored; it is always derived via DB aggregation.
    - A DEBIT is created atomically with the Payout row (same transaction).
    - A CREDIT reversal is created atomically with a FAILED state transition.
    """

    class EntryType(models.TextChoices):
        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    # BigIntegerField — stores paise. NEVER FloatField, NEVER DecimalField.
    amount = models.BigIntegerField()
    description = models.CharField(max_length=500, blank=True)
    # Nullable FK: DEBITs and reversal CREDITs link back to the payout.
    payout = models.ForeignKey(
        "payouts.Payout",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ledger_entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["merchant", "created_at"]),
            models.Index(fields=["merchant", "entry_type"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="ledger_amount_must_be_positive",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and LedgerEntry.objects.filter(pk=self.pk).exists():
            raise PermissionError(
                "LedgerEntry is immutable — updates are forbidden."
            )
        if self.amount is not None and self.amount <= 0:
            raise ValueError("LedgerEntry amount must be a positive integer (paise).")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("LedgerEntry is immutable — deletion is forbidden.")

    def __str__(self):
        return f"[{self.entry_type}] {self.amount} paise — {self.merchant}"
