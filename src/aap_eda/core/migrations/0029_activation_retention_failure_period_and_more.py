# Generated by Django 4.2.7 on 2024-03-25 21:50

import django.core.validators
from django.db import migrations, models

import aap_eda.core.models.activation
import aap_eda.core.models.event_stream


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_activation_restart_completion_interval_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="retention_failure_period",
            field=models.IntegerField(
                default=aap_eda.core.models.activation.RetentionFailurePeriod[
                    "SETTINGS"
                ],
                validators=[
                    django.core.validators.MinValueValidator(
                        limit_value=aap_eda.core.models.activation.RetentionFailurePeriod[
                            "MINIMUM"
                        ],
                        message="The retention period for failiures specifies the length of time, in hours, an individual failureresult will be retained; it must be an integer greater than or equal to -1; system settings = 0, forever = -1, default = 0",
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="activation",
            name="retention_success_period",
            field=models.IntegerField(
                default=aap_eda.core.models.activation.RetentionSuccessPeriod[
                    "SETTINGS"
                ],
                validators=[
                    django.core.validators.MinValueValidator(
                        limit_value=aap_eda.core.models.activation.RetentionSuccessPeriod[
                            "MINIMUM"
                        ],
                        message="The retention period for successes specifies the length of time, in hours, an individual successresult will be retained; it must be an integer greater than or equal to -1; system settings = 0, forever = -1, default = 0",
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="eventstream",
            name="retention_failure_period",
            field=models.IntegerField(
                default=aap_eda.core.models.event_stream.RetentionFailurePeriod[
                    "SETTINGS"
                ],
                validators=[
                    django.core.validators.MinValueValidator(
                        limit_value=aap_eda.core.models.event_stream.RetentionFailurePeriod[
                            "MINIMUM"
                        ],
                        message="The retention period for failiures specifies the length of time, in hours, an individual failureresult will be retained; it must be an integer greater than or equal to -1; system settings = 0, forever = -1, default = 0",
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="eventstream",
            name="retention_success_period",
            field=models.IntegerField(
                default=aap_eda.core.models.event_stream.RetentionSuccessPeriod[
                    "SETTINGS"
                ],
                validators=[
                    django.core.validators.MinValueValidator(
                        limit_value=aap_eda.core.models.event_stream.RetentionSuccessPeriod[
                            "MINIMUM"
                        ],
                        message="The retention period for successes specifies the length of time, in hours, an individual successresult will be retained; it must be an integer greater than or equal to -1; system settings = 0, forever = -1, default = 0",
                    )
                ],
            ),
        ),
    ]
