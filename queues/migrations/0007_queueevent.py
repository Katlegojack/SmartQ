# Generated manually for Day 36 QueueEvent audit history.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0004_guestcustomer_booking_guest_customer_booking_source_and_constraint"),
        ("counters", "0003_counter_assigned_staff"),
        ("queues", "0006_queueticket_scheduled_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QueueEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("ticket_scheduled", "Ticket Scheduled"), ("checked_in", "Checked In"), ("called", "Called"), ("completed", "Completed"), ("no_show", "No Show"), ("cancelled", "Cancelled"), ("rescheduled", "Rescheduled"), ("disruption_rescheduled", "Disruption Rescheduled"), ("counter_opened", "Counter Opened"), ("counter_paused", "Counter Paused"), ("counter_resumed", "Counter Resumed"), ("counter_closed", "Counter Closed"), ("counter_staff_assigned", "Counter Staff Assigned"), ("counter_staff_unassigned", "Counter Staff Unassigned")], max_length=40)),
                ("source", models.CharField(choices=[("system", "System"), ("customer", "Customer"), ("staff", "Staff")], default="system", max_length=20)),
                ("actor_username", models.CharField(blank=True, max_length=150)),
                ("actor_role", models.CharField(blank=True, max_length=40)),
                ("from_ticket_status", models.CharField(blank=True, max_length=20)),
                ("to_ticket_status", models.CharField(blank=True, max_length=20)),
                ("from_booking_status", models.CharField(blank=True, max_length=20)),
                ("to_booking_status", models.CharField(blank=True, max_length=20)),
                ("queue_number", models.CharField(blank=True, max_length=10)),
                ("queue_type", models.CharField(blank=True, max_length=20)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("occurred_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_events_created", to=settings.AUTH_USER_MODEL)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_events", to="bookings.booking")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_events", to="branches.branch")),
                ("counter", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_events", to="counters.counter")),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="queue_events", to="services.service")),
                ("ticket", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="queues.queueticket")),
            ],
            options={
                "ordering": ["occurred_at", "id"],
            },
        ),
        migrations.AddIndex(model_name="queueevent", index=models.Index(fields=["branch", "occurred_at"], name="queue_evt_branch_time")),
        migrations.AddIndex(model_name="queueevent", index=models.Index(fields=["booking", "occurred_at"], name="queue_evt_booking_time")),
        migrations.AddIndex(model_name="queueevent", index=models.Index(fields=["ticket", "occurred_at"], name="queue_evt_ticket_time")),
        migrations.AddIndex(model_name="queueevent", index=models.Index(fields=["counter", "occurred_at"], name="queue_evt_counter_time")),
        migrations.AddIndex(model_name="queueevent", index=models.Index(fields=["event_type", "occurred_at"], name="queue_evt_type_time")),
    ]
