from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0074_awxtoken_ck_awx_token_name_not_empty_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookprocess",
            name="activation_job_namespace",
            field=models.TextField(null=True),
        ),
    ]
