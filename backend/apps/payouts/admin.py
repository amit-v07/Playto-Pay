from django.contrib import admin
from apps.payouts.models import Payout, PayoutAuditLog, IdempotencyKey


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "amount", "status", "retry_count", "created_at"]
    list_filter = ["status", "merchant"]
    search_fields = ["merchant__business_name"]
    readonly_fields = ["id", "merchant", "amount", "idempotency_key", "created_at", "updated_at"]


@admin.register(PayoutAuditLog)
class PayoutAuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "payout", "actor", "old_status", "new_status", "created_at"]
    readonly_fields = ["id", "payout", "actor", "old_status", "new_status", "metadata", "created_at"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ["key", "merchant", "status", "expires_at", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["id", "created_at"]
