# Generated by Django 4.2.7 on 2024-09-16 19:40

from django.db import migrations, models

import aap_eda.core.utils.crypto.fields


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0050_update_credential_type_help_text"),
    ]

    operations = [
        migrations.CreateModel(
            name="Setting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=255, unique=True)),
                (
                    "value",
                    aap_eda.core.utils.crypto.fields.EncryptedTextField(
                        blank=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("modified_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "core_setting",
                "indexes": [
                    models.Index(
                        fields=["key"], name="core_settin_key_53fa74_idx"
                    )
                ],
            },
        ),
    ]
