import uuid
from django.db import models
from django.contrib.auth.models import User


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="merchant")
    business_name = models.CharField(max_length=255)
    webhook_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchants"

    def __str__(self):
        return self.business_name

    def get_balance(self) -> int:
        """
        Always computes balance via DB aggregation — never Python arithmetic.
        Returns paise (integer).
        """
        from apps.ledger.models import LedgerEntry
        from django.db.models import Sum, Q

        result = LedgerEntry.objects.filter(merchant=self).aggregate(
            credits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.CREDIT)),
            debits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.DEBIT)),
        )
        return (result["credits"] or 0) - (result["debits"] or 0)
