from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rescheduling", "0002_rescheduleoption"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rescheduleoption",
            name="option_time",
            field=models.TimeField(),
        ),
    ]
