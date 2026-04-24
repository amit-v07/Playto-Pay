import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("merchants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ledger_entries",
                        to="merchants.merchant",
                    ),
                ),
                (
                    "entry_type",
                    models.CharField(
                        choices=[("CREDIT", "Credit"), ("DEBIT", "Debit")],
                        max_length=10,
                    ),
                ),
                ("amount", models.BigIntegerField()),
                ("description", models.CharField(blank=True, max_length=500)),
                # payout FK added in migration 0002 to avoid circular dependency
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ledger_entries",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["merchant", "created_at"], name="ledger_entries_merchant_created_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["merchant", "entry_type"], name="ledger_entries_merchant_type_idx"),
        ),
        migrations.AddConstraint(
            model_name="ledgerentry",
            constraint=models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="ledger_amount_must_be_positive",
            ),
        ),
    ]
