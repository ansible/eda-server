# Generated by Django 4.2.7 on 2024-03-04 23:34

from django.db import migrations, models

import aap_eda.core.enums
import aap_eda.core.utils.crypto.fields


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_activation_log_level_eventstream_log_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="credential",
            name="scm_ssh_key",
            field=aap_eda.core.utils.crypto.fields.EncryptedTextField(
                null=True
            ),
        ),
        migrations.AddField(
            model_name="credential",
            name="scm_ssh_key_password",
            field=aap_eda.core.utils.crypto.fields.EncryptedTextField(
                null=True
            ),
        ),
        migrations.AlterField(
            model_name="credential",
            name="credential_type",
            field=models.TextField(
                choices=[
                    ("Container Registry", "Container Registry"),
                    (
                        "GitHub Personal Access Token",
                        "GitHub Personal Access Token",
                    ),
                    (
                        "GitLab Personal Access Token",
                        "GitLab Personal Access Token",
                    ),
                    ("Vault", "Vault"),
                    ("Generic SCM Credential", "Generic SCM Credential"),
                ],
                default=aap_eda.core.enums.CredentialType["REGISTRY"],
            ),
        ),
        migrations.AlterField(
            model_name="credential",
            name="secret",
            field=aap_eda.core.utils.crypto.fields.EncryptedTextField(
                null=True
            ),
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.CheckConstraint(
                check=models.Q(
                    (
                        "credential_type",
                        aap_eda.core.enums.CredentialType["SCM"],
                    ),
                    models.Q(
                        ("secret__isnull", False),
                        models.Q(("secret", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="ck_empty_secret",
            ),
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        (
                            "credential_type",
                            aap_eda.core.enums.CredentialType["SCM"],
                        ),
                        _negated=True,
                    ),
                    models.Q(
                        models.Q(
                            ("scm_ssh_key__isnull", True),
                            ("scm_ssh_key", ""),
                            _connector="OR",
                        ),
                        models.Q(
                            ("scm_ssh_key_password__isnull", True),
                            ("scm_ssh_key_password", ""),
                            _connector="OR",
                        ),
                        ("secret__isnull", False),
                        models.Q(("secret", ""), _negated=True),
                    ),
                    models.Q(
                        ("scm_ssh_key__isnull", False),
                        models.Q(("scm_ssh_key", ""), _negated=True),
                        ("scm_ssh_key_password__isnull", False),
                        models.Q(("scm_ssh_key_password", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="ck_scm_credential",
            ),
        ),
    ]
