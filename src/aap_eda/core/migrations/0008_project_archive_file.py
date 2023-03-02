from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_remove_large_data_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="archive_file",
            field=models.FileField(default="", upload_to="projects/"),
            preserve_default=False,
        ),
    ]
