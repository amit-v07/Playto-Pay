from rest_framework import serializers
from apps.payouts.models import Payout, PayoutAuditLog, IdempotencyKey


class PayoutAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutAuditLog
        fields = ["id", "actor", "old_status", "new_status", "metadata", "created_at"]


class PayoutSerializer(serializers.ModelSerializer):
    amount_inr = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id", "amount", "amount_inr", "status",
            "failure_reason", "retry_count",
            "processing_started_at", "created_at", "updated_at",
        ]

    def get_amount_inr(self, obj) -> str:
        return f"₹{obj.amount / 100:.2f}"


class PayoutDetailSerializer(PayoutSerializer):
    audit_logs = PayoutAuditLogSerializer(many=True, read_only=True)

    class Meta(PayoutSerializer.Meta):
        fields = PayoutSerializer.Meta.fields + ["audit_logs"]


class CreatePayoutSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=100,
        help_text="Amount to withdraw, in paise. Minimum 100 paise (₹1).",
    )
