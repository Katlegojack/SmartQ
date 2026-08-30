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
        migrations.AddConstraint(
            model_name="profile",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        role__in=["receptionist", "counter_staff", "branch_manager"],
                        branch__isnull=False,
                    )
                    | models.Q(
                        role__in=["customer", "system_admin"],
                        branch__isnull=True,
                    )
                ),
                name="profile_role_has_valid_branch_scope",
            ),
        ),
    ]
