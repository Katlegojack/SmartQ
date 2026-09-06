from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0001_initial"),
        ("queues", "0009_queueticket_service_timing"),
        ("services", "0003_branchservice"),
    ]

    operations = [
        migrations.CreateModel(
            name="QueueForecastObservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("queue_type", models.CharField(choices=[("general", "General"), ("priority", "Priority")], max_length=20)),
                ("booking_source", models.CharField(max_length=20)),
                ("checked_in_at", models.DateTimeField(db_index=True)),
                ("baseline_estimated_wait_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("people_ahead", models.PositiveIntegerField(default=0)),
                ("open_counter_count", models.PositiveIntegerField(default=0)),
                ("serving_count", models.PositiveIntegerField(default=0)),
                ("called_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("actual_wait_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("wait_variance_seconds", models.IntegerField(blank=True, null=True)),
                ("service_target_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("service_completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("actual_service_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("service_variance_seconds", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="queue_forecast_observations",
                        to="branches.branch",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="queue_forecast_observations",
                        to="services.service",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forecast_observations",
                        to="queues.queueticket",
                    ),
                ),
            ],
            options={
                "ordering": ["checked_in_at", "id"],
                "indexes": [
                    models.Index(fields=["branch", "checked_in_at"], name="queue_fc_branch_time"),
                    models.Index(fields=["service", "checked_in_at"], name="queue_fc_service_time"),
                ],
            },
        ),
    ]
