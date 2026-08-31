from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0001_initial"),
        ("services", "0002_rename_average_time_service_average_service_time"),
    ]

    operations = [
        migrations.CreateModel(
            name="BranchService",
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
                (
                    "max_bookings_per_slot",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_mappings",
                        to="branches.branch",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="branch_mappings",
                        to="services.service",
                    ),
                ),
            ],
            options={
                "ordering": ["branch__name", "service__name"],
            },
        ),
        migrations.AddConstraint(
            model_name="branchservice",
            constraint=models.UniqueConstraint(
                fields=("branch", "service"),
                name="unique_branch_service_mapping",
            ),
        ),
    ]
