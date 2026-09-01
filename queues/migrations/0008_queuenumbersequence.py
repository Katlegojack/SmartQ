from django.db import migrations, models
import django.db.models.deletion


def backfill_queue_number_sequences(apps, schema_editor):
    QueueTicket = apps.get_model("queues", "QueueTicket")
    QueueNumberSequence = apps.get_model("queues", "QueueNumberSequence")

    highest_numbers = {}
    tickets = QueueTicket.objects.exclude(booking_id=None).values_list(
        "booking__branch_id",
        "booking__booking_date",
        "queue_type",
        "queue_number",
    )

    for branch_id, booking_date, queue_type, queue_number in tickets.iterator():
        if not queue_number or len(queue_number) < 2:
            continue
        try:
            number = int(queue_number[1:])
        except (TypeError, ValueError):
            continue

        key = (branch_id, booking_date, queue_type)
        highest_numbers[key] = max(highest_numbers.get(key, 0), number)

    QueueNumberSequence.objects.bulk_create(
        [
            QueueNumberSequence(
                branch_id=branch_id,
                booking_date=booking_date,
                queue_type=queue_type,
                last_number=last_number,
            )
            for (branch_id, booking_date, queue_type), last_number in highest_numbers.items()
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("queues", "0007_queueevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="QueueNumberSequence",
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
                ("booking_date", models.DateField()),
                (
                    "queue_type",
                    models.CharField(
                        choices=[("general", "General"), ("priority", "Priority")],
                        max_length=20,
                    ),
                ),
                ("last_number", models.PositiveIntegerField(default=0)),
                (
                    "branch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="queue_number_sequences",
                        to="branches.branch",
                    ),
                ),
            ],
            options={
                "ordering": ["branch_id", "booking_date", "queue_type"],
            },
        ),
        migrations.AddConstraint(
            model_name="queuenumbersequence",
            constraint=models.UniqueConstraint(
                fields=("branch", "booking_date", "queue_type"),
                name="unique_queue_number_sequence",
            ),
        ),
        migrations.RunPython(
            backfill_queue_number_sequences,
            migrations.RunPython.noop,
        ),
    ]
