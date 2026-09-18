from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0073_activation_k8s_pod_tolerations"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="k8s_pod_affinity",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Kubernetes affinity rules (nodeAffinity, podAffinity, "
                    "podAntiAffinity) applied to activation job pods for "
                    "scheduling constraints."
                ),
            ),
        ),
    ]
