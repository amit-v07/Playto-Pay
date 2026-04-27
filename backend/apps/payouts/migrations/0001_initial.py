import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Creates IdempotencyKey, Payout, and PayoutAuditLog.
    These all live in the payouts app.
    Depends on merchants and ledger (0001) being applied first.
    """

    initial = True

    dependencies = [
        ("merchants", "0001_initial"),
        ("ledger", "0001_initial"),
    ]

    operations = [
        # ── IdempotencyKey ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="idempotency_keys",
                        to="merchants.merchant",
                    ),
                ),
                ("key", models.UUIDField()),
                (
                    "status",
                    models.CharField(
                        choices=[("IN_PROGRESS", "In Progress"), ("DONE", "Done")],
                        default="IN_PROGRESS",
                        max_length=20,
                    ),
                ),
                ("request_hash", models.CharField(blank=True, max_length=64)),
                ("response_status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "idempotency_keys",
            },
        ),
        migrations.AlterUniqueTogether(
            name="idempotencykey",
            unique_together={("merchant", "key")},
        ),
        migrations.AddIndex(
            model_name="idempotencykey",
            index=models.Index(fields=["merchant", "key"], name="idempotency_keys_merchant_key_idx"),
        ),
        migrations.AddIndex(
            model_name="idempotencykey",
            index=models.Index(fields=["expires_at"], name="idempotency_keys_expires_at_idx"),
        ),

        # ── Payout ────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "merchant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payouts",
                        to="merchants.merchant",
                    ),
                ),
                ("amount", models.BigIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "idempotency_key",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout",
                        to="payouts.idempotencykey",
                    ),
                ),
                ("failure_reason", models.TextField(blank=True, null=True)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "payouts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="payout",
            index=models.Index(fields=["merchant", "status"], name="payouts_merchant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="payout",
            index=models.Index(fields=["status", "processing_started_at"], name="payouts_status_started_at_idx"),
        ),
        migrations.AddConstraint(
            model_name="payout",
            constraint=models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="payout_amount_must_be_positive",
            ),
        ),

        # ── PayoutAuditLog ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="PayoutAuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "payout",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_logs",
                        to="payouts.payout",
                    ),
                ),
                ("actor", models.CharField(max_length=100)),
                ("old_status", models.CharField(blank=True, max_length=20, null=True)),
                ("new_status", models.CharField(max_length=20)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "payout_audit_logs",
                "ordering": ["created_at"],
            },
        ),

    ]
