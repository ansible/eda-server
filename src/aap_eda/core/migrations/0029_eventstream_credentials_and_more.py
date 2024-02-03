# Generated by Django 4.2.7 on 2024-02-06 21:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_remove_eventstream_awx_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventstream",
            name="credentials",
            field=models.ManyToManyField(
                default=None,
                related_name="event_streams",
                to="core.credential",
            ),
        ),
        migrations.AlterField(
            model_name="eventstream",
            name="channel_name",
            field=models.TextField(default=None, null=True),
        ),
    ]