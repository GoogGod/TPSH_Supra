from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0003_waiterslot_employee_level"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scheduleentry",
            name="shift_type",
            field=models.CharField(
                choices=[
                    ("off", "Выходной"),
                    ("full", "Полная"),
                    ("morning", "Утренняя"),
                    ("evening", "Вечерняя"),
                    ("custom", "Произвольная"),
                ],
                default="off",
                max_length=10,
                verbose_name="Тип смены",
            ),
        ),
    ]
