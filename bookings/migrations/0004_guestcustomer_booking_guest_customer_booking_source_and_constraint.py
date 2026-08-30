import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0003_booking_checked_in_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="GuestCustomer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=150)),
                ("phone_number", models.CharField(blank=True, max_length=30)),
                ("date_of_birth", models.DateField()),
                (
                    "gender",
                    models.CharField(
                        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
                        max_length=20,
                    ),
                ),
                ("disability_status", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterField(
            model_name="booking",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="guest_customer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bookings",
                to="bookings.guestcustomer",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="source",
            field=models.CharField(
                choices=[("online", "Online"), ("walk_in", "Walk-in")],
                default="online",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("guest_customer__isnull", True), ("user__isnull", False))
                    | models.Q(("guest_customer__isnull", False), ("user__isnull", True))
                ),
                name="booking_has_exactly_one_customer_identity",
            ),
        ),
    ]
