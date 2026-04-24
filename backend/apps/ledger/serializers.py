from rest_framework import serializers
from apps.ledger.models import LedgerEntry


class LedgerEntrySerializer(serializers.ModelSerializer):
    amount_inr = serializers.SerializerMethodField()
    payout_id = serializers.UUIDField(source="payout.id", read_only=True, default=None)

    class Meta:
        model = LedgerEntry
        fields = [
            "id", "entry_type", "amount", "amount_inr",
            "description", "payout_id", "created_at",
        ]

    def get_amount_inr(self, obj) -> str:
        return f"₹{obj.amount / 100:.2f}"


class CreditSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1, help_text="Amount in paise (e.g. 10000 = ₹100)")
    description = serializers.CharField(max_length=500, default="Payment received")
