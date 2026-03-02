import hashlib

from django.db import migrations, models


def _compute_sha256(content):
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def populate_rulesets_sha256(apps, schema_editor):
    """Compute SHA256 for existing records that lack it."""
    Rulebook = apps.get_model("core", "Rulebook")  # noqa: N806
    for rb in Rulebook.objects.filter(rulesets_sha256="").iterator(
        chunk_size=500
    ):
        rb.rulesets_sha256 = _compute_sha256(rb.rulesets)
        rb.save(update_fields=["rulesets_sha256"])

    Activation = apps.get_model("core", "Activation")  # noqa: N806
    for act in Activation.objects.filter(rulebook_rulesets_sha256="").iterator(
        chunk_size=500
    ):
        act.rulebook_rulesets_sha256 = _compute_sha256(act.rulebook_rulesets)
        act.save(update_fields=["rulebook_rulesets_sha256"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0068_add_project_sync_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="activation",
            name="restart_on_project_update",
            field=models.BooleanField(
                default=False,
                help_text="Auto-restart when rulebook changes after project sync",
            ),
        ),
        migrations.AddField(
            model_name="activation",
            name="awaiting_project_sync",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Activation is waiting for project "
                    "sync to complete before launch"
                ),
            ),
        ),
        migrations.AddField(
            model_name="rulebook",
            name="rulesets_sha256",
            field=models.CharField(
                default="",
                help_text="SHA256 hash of rulesets content",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="activation",
            name="rulebook_rulesets_sha256",
            field=models.CharField(
                default="",
                help_text="SHA256 hash of original rulebook content",
                max_length=64,
            ),
        ),
        migrations.RunPython(
            populate_rulesets_sha256,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
