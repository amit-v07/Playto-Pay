import pytest
from django.contrib.auth.models import User

from apps.merchants.models import Merchant
from apps.ledger.models import LedgerEntry


@pytest.fixture
def make_merchant(db):
    """Factory fixture: creates a merchant with an optional initial balance."""
    def _make(username="testmerchant", business_name="Test Biz", balance_paise=0):
        user = User.objects.create_user(username=username, password="testpass123")
        merchant = Merchant.objects.create(user=user, business_name=business_name)
        if balance_paise > 0:
            LedgerEntry.objects.create(
                merchant=merchant,
                entry_type=LedgerEntry.EntryType.CREDIT,
                amount=balance_paise,
                description="Test initial credit",
            )
        return merchant
    return _make


@pytest.fixture
def merchant(make_merchant):
    return make_merchant(balance_paise=1_000_000)  # ₹10,000 initial balance


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, merchant):
    """API client authenticated as the test merchant."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(merchant.user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client.merchant = merchant
    return api_client
