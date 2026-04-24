import logging

from django.db import transaction
from django.db.models import Sum, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from apps.ledger.models import LedgerEntry
from apps.ledger.serializers import LedgerEntrySerializer, CreditSerializer
from apps.merchants.models import Merchant

logger = logging.getLogger(__name__)


class BalanceView(APIView):
    """
    Returns the merchant's current balance.
    Balance is ALWAYS computed via DB aggregation — never stored, never Python arithmetic.
    """

    def get(self, request):
        merchant: Merchant = request.user.merchant
        result = LedgerEntry.objects.filter(merchant=merchant).aggregate(
            credits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.CREDIT)),
            debits=Sum("amount", filter=Q(entry_type=LedgerEntry.EntryType.DEBIT)),
        )
        credits = result["credits"] or 0
        debits = result["debits"] or 0
        balance_paise = credits - debits
        return Response({
            "balance_paise": balance_paise,
            "balance_inr": f"₹{balance_paise / 100:.2f}",
            "total_credits_paise": credits,
            "total_debits_paise": debits,
        })


class CreditView(APIView):
    """
    Simulates an incoming payment (credit) to the merchant's ledger.
    In production this would be triggered by a payment gateway webhook.
    """

    def post(self, request):
        serializer = CreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        merchant: Merchant = request.user.merchant
        amount: int = serializer.validated_data["amount"]
        description: str = serializer.validated_data.get("description", "Payment received")

        with transaction.atomic():
            entry = LedgerEntry.objects.create(
                merchant=merchant,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount=amount,
                description=description,
            )

        logger.info(f"[CreditView] Created credit of {amount} paise for merchant {merchant.id}")
        return Response(LedgerEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class TransactionListView(ListAPIView):
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        merchant: Merchant = self.request.user.merchant
        qs = LedgerEntry.objects.filter(merchant=merchant)

        entry_type = self.request.query_params.get("type")
        if entry_type in (LedgerEntry.EntryType.CREDIT, LedgerEntry.EntryType.DEBIT):
            qs = qs.filter(entry_type=entry_type)

        return qs
