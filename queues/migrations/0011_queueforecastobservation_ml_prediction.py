from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queues", "0010_queueforecastobservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="queueforecastobservation",
            name="ml_estimated_wait_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueforecastobservation",
            name="prediction_model",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="queueforecastobservation",
            name="prediction_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueforecastobservation",
            name="ml_wait_variance_seconds",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
