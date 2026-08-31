# Generated for Smart Q Day 33 counter lifecycle.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("counters", "0002_counter_queue_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="counter",
            name="branch",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="counters",
                to="branches.branch",
            ),
        ),
        migrations.AddField(
            model_name="counter",
            name="assigned_staff",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_counter",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
