from django.contrib import admin
from apps.merchants.models import Merchant


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ["business_name", "user", "webhook_url", "created_at"]
    search_fields = ["business_name", "user__username"]
    readonly_fields = ["id", "created_at"]
