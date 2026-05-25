from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0072_activation_k8s_pod_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="k8s_pod_tolerations",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Kubernetes tolerations applied to activation job "
                    "pods so they can be scheduled onto tainted nodes."
                ),
            ),
        ),
    ]
