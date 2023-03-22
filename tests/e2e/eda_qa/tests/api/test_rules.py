import pytest

from eda_api.models import Project
from eda_qa.api import api_client


# TODO: update the client and fix this test after fix: https://issues.redhat.com/browse/AAP-9995
@pytest.mark.qa
@pytest.mark.api
def test_list_rules(default_project_rules: list[dict], new_project: Project):
    """
    Check the correct listing of rules
    """
    response = api_client.rules.list()

    assert response.status_code == 200

    # Filter by project
    # TODO: change when filtering and pagination is implemented https://issues.redhat.com/browse/AAP-5603
    rules = [rule for rule in response.data if rule.project.id == new_project.id]

    assert len(rules) == len(default_project_rules)

    # sort all rules to verify the names
    sorted_rules = sorted(rules, key=lambda k: k["name"])
    sorted_expected_rules = sorted(default_project_rules, key=lambda k: k["name"])

    for rule, expected_rule in zip(sorted_rules, sorted_expected_rules):
        assert rule["name"] == expected_rule["name"]
        assert rule["ruleset"]["name"] == expected_rule["ruleset"]
        assert rule["rulebook"]["name"] == expected_rule["rulebook"]


# TODO: update the client and fix this test after fix: https://issues.redhat.com/browse/AAP-9995
@pytest.mark.qa
@pytest.mark.api
def test_show_rule(default_project_rules: list[dict], new_project):
    """
    Verify the correct showing of a rule
    """

    rules_list = api_client.rules.list().data

    # Filter by project
    # TODO: change when filtering and pagination is implemented https://issues.redhat.com/browse/AAP-5603
    rules = [rule for rule in rules_list if rule.project.id == new_project.id]

    # Get a rule:
    rule_id = rules[0].id

    request = api_client.rules.read(rule_id)

    assert request.status_code == 200

    expected_rule = next(
        rule for rule in default_project_rules if rule["name"] == request.data.name
    )

    assert request.data.project.id == new_project.id
    assert request.data["ruleset"]["name"] == expected_rule["ruleset"]
    assert request.data["rulebook"]["name"] == expected_rule["rulebook"]
    assert request.data.action == expected_rule["action"]

    # TODO: assert conditions https://issues.redhat.com/browse/AAP-5832
