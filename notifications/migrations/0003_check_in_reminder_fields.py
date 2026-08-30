import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_guestcustomer_booking_guest_customer_booking_source_and_constraint"),
        ("notifications", "0002_notification_message"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="related_booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="bookings.booking",
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("queue_update", "Queue Update"),
                    ("disruption", "Disruption"),
                    ("reschedule", "Reschedule"),
                    ("check_in_reminder", "Check-in Reminder"),
                ],
                default="general",
                max_length=100,
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("notification_type", "check_in_reminder"),
                    ("related_booking__isnull", False),
                    ("reminder_at__isnull", False),
                ),
                fields=("related_booking", "reminder_at"),
                name="unique_booking_check_in_reminder_slot",
            ),
        ),
    ]
