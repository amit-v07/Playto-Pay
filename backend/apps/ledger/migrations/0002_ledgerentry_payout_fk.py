import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds the payout FK to LedgerEntry. 
    This is in a separate migration to resolve the circular dependency 
    between ledger and payouts apps.
    """

    dependencies = [
        ("ledger", "0001_initial"),
        ("payouts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ledgerentry",
            name="payout",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ledger_entries",
                to="payouts.payout",
            ),
        ),
    ]
