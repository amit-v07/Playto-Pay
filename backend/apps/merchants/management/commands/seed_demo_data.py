import logging

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from apps.merchants.models import Merchant
from apps.ledger.models import LedgerEntry

logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "username": "alice",
        "password": "password123",
        "email": "alice@playtopay.dev",
        "business_name": "Alice's Boutique",
        "webhook_url": "https://webhook.site/playtopay-alice",
        "initial_credits": [
            (500000, "Razorpay settlement batch #1"),
            (250000, "Razorpay settlement batch #2"),
        ],
    },
    {
        "username": "bob",
        "password": "password123",
        "email": "bob@playtopay.dev",
        "business_name": "Bob's Electronics",
        "webhook_url": None,
        "initial_credits": [
            (1000000, "Initial payment gateway credit"),
        ],
    },
]


class Command(BaseCommand):
    help = "Seeds the database with demo merchants and ledger entries for development."

    def handle(self, *args, **options):
        for data in DEMO_USERS:
            with transaction.atomic():
                if User.objects.filter(username=data["username"]).exists():
                    self.stdout.write(f"  [skip] User '{data['username']}' already exists.")
                    continue

                user = User.objects.create_user(
                    username=data["username"],
                    password=data["password"],
                    email=data["email"],
                )
                merchant = Merchant.objects.create(
                    user=user,
                    business_name=data["business_name"],
                    webhook_url=data.get("webhook_url"),
                )
                for amount, description in data["initial_credits"]:
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        amount=amount,
                        description=description,
                    )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [ok] Created merchant '{data['business_name']}' "
                        f"(username={data['username']}, password={data['password']})"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
