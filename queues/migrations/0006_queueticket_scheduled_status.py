from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("queues", "0005_queuedisruptionimpact"),
    ]

    operations = [
        migrations.AlterField(
            model_name="queueticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Scheduled"),
                    ("waiting", "Waiting"),
                    ("serving", "Serving"),
                    ("completed", "Completed"),
                    ("no_show", "No Show"),
                    ("cancelled", "Cancelled"),
                ],
                default="scheduled",
                max_length=20,
            ),
        ),
    ]
