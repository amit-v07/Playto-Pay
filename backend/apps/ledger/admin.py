from django.contrib import admin
from apps.ledger.models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "merchant", "entry_type", "amount", "description", "created_at"]
    list_filter = ["entry_type", "merchant"]
    search_fields = ["merchant__business_name", "description"]
    readonly_fields = ["id", "created_at", "merchant", "entry_type", "amount", "payout"]

    def has_change_permission(self, request, obj=None):
        return False  # Immutable

    def has_delete_permission(self, request, obj=None):
        return False  # Immutable
