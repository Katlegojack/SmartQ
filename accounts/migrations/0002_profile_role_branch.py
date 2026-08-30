from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("branches", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="branch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="staff_profiles",
                to="branches.branch",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="role",
            field=models.CharField(
                choices=[
                    ("customer", "Customer"),
                    ("receptionist", "Receptionist"),
                    ("counter_staff", "Counter Staff"),
                    ("branch_manager", "Branch Manager"),
                    ("system_admin", "System Administrator"),
                ],
                default="customer",
                max_length=30,
            ),
        ),
    ]
