from django.urls import path
from apps.payouts.views import CreatePayoutView, PayoutListView, PayoutDetailView

urlpatterns = [
    path("", CreatePayoutView.as_view(), name="payout-create"),
    path("list/", PayoutListView.as_view(), name="payout-list"),
    path("<uuid:id>/", PayoutDetailView.as_view(), name="payout-detail"),
]
