from http import HTTPStatus

import pytest

from eda_api.model.project_read import ProjectRead
from eda_qa.api import api_client


@pytest.mark.xfail(reason="Needs clarification about the parent relations")
@pytest.mark.qa
@pytest.mark.api
def test_list_rulesets(new_project: ProjectRead, default_project_rulesets: list[dict]):
    """
    Test the correct listing of rulesets
    """

    rulesets = []

    # Rulesets are populated at project import, fetch rulesets from the project
    # TODO: needs clarification about the relation with project and rulebook
    for page in api_client.rulesets.iter_pages():
        assert page.status_code == HTTPStatus.OK
        rulesets.extend([ruleset for ruleset in page.results if ruleset.project == new_project.id])

    assert len(rulesets) == len(default_project_rulesets)

    # sort by name to have predictable results
    sorted_rulesets = sorted(rulesets, key=lambda k: k["name"])
    sorted_default_rulesets = sorted(default_project_rulesets, key=lambda k: k["name"])

    # content verification
    for ruleset, expected in zip(sorted_rulesets, sorted_default_rulesets):
        assert ruleset["name"] == expected["name"]
        assert ruleset["rule_count"] == len(expected["rules"])
        # TODO: verify the rest of the fields


@pytest.mark.qa
@pytest.mark.api
def test_read_ruleset(new_project: ProjectRead, default_project_rulesets: list[dict]):
    """
    Test the correct fetch of a ruleset
    """
    # TODO: It requires a fixture to get a new rulebook, which requires first
    # to implement tests and client for rulebooks
    pass
