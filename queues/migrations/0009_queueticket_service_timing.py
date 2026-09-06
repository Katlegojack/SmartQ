from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queues", "0008_queuenumbersequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="queueticket",
            name="service_started_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="queueticket",
            name="service_completed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="queueticket",
            name="service_target_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueticket",
            name="actual_service_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueticket",
            name="service_variance_seconds",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
