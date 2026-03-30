from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(role="employee").update(role="employee_noob")


def backwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(
        role__in=["employee_noob", "employee_pro"]
    ).update(role="employee")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_role_choices"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]