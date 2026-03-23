import hashlib

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from aap_eda.core import models


def _sha256(content):
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def get_historical_model(app_label, model_name, migration):
    """Get model as it existed at a specific migration."""
    executor = MigrationExecutor(connection)
    state = executor.loader.project_state((app_label, migration))
    return state.apps.get_model(app_label, model_name)


@pytest.fixture
def rollback_migration():
    """Rollback to pre-0069 state and restore after test."""
    call_command("migrate", "core", "0068")
    yield
    call_command("migrate")


@pytest.mark.django_db(transaction=True)
def test_migration_populates_rulebook_hash(
    rollback_migration,
    default_organization,
):
    """Migration computes SHA256 for existing Rulebook rows."""
    HistoricalRulebook = get_historical_model(  # noqa: N806
        "core",
        "Rulebook",
        "0068_add_project_sync_fields",
    )

    content = "---\n- name: test\n  hosts: all\n"
    rb = HistoricalRulebook.objects.create(
        name="test-rb",
        rulesets=content,
        organization_id=default_organization.id,
    )

    call_command("migrate", "core", "0069")

    rb_fresh = models.Rulebook.objects.get(pk=rb.pk)
    assert rb_fresh.rulesets_sha256 == _sha256(content)
    assert len(rb_fresh.rulesets_sha256) == 64


@pytest.mark.django_db(transaction=True)
def test_migration_populates_activation_hash(
    rollback_migration,
    default_organization,
):
    """Migration computes SHA256 for existing Activation rows."""
    HistoricalRulebook = get_historical_model(  # noqa: N806
        "core",
        "Rulebook",
        "0068_add_project_sync_fields",
    )
    HistoricalActivation = get_historical_model(  # noqa: N806
        "core",
        "Activation",
        "0068_add_project_sync_fields",
    )

    content = "rule-content"
    rb = HistoricalRulebook.objects.create(
        name="test-rb",
        rulesets=content,
        organization_id=default_organization.id,
    )
    act = HistoricalActivation.objects.create(
        name="test-act",
        rulebook_id=rb.pk,
        rulebook_name=rb.name,
        rulebook_rulesets=content,
        organization_id=default_organization.id,
    )

    call_command("migrate", "core", "0069")

    # Use historical model to avoid accessing fields from later migrations
    HistoricalActivation0069 = get_historical_model(  # noqa: N806
        "core",
        "Activation",
        "0069_activation_restart_and_sync_fields",
    )
    act_fresh = HistoricalActivation0069.objects.get(pk=act.pk)
    assert act_fresh.rulebook_rulesets_sha256 == (_sha256(content))


@pytest.mark.django_db(transaction=True)
def test_migration_handles_empty_rulesets(
    rollback_migration,
    default_organization,
):
    """Migration handles empty rulesets content."""
    HistoricalRulebook = get_historical_model(  # noqa: N806
        "core",
        "Rulebook",
        "0068_add_project_sync_fields",
    )

    rb = HistoricalRulebook.objects.create(
        name="empty-rb",
        rulesets="",
        organization_id=default_organization.id,
    )

    call_command("migrate", "core", "0069")

    rb_fresh = models.Rulebook.objects.get(pk=rb.pk)
    assert rb_fresh.rulesets_sha256 == _sha256("")
    assert len(rb_fresh.rulesets_sha256) == 64
