# Generated by Django 4.2.7 on 2024-02-12 19:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_remove_eventstream_listener_args_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="eventstream",
            old_name="args",
            new_name="source_args",
        ),
    ]
