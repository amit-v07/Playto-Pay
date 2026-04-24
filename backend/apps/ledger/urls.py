from django.urls import path
from apps.ledger.views import BalanceView, CreditView, TransactionListView

urlpatterns = [
    path("balance/", BalanceView.as_view(), name="ledger-balance"),
    path("credit/", CreditView.as_view(), name="ledger-credit"),
    path("transactions/", TransactionListView.as_view(), name="ledger-transactions"),
]
