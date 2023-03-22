import nanoid
import pytest
import yaml

from eda_qa.api import api_client
from eda_qa.utils.projects import get_project_file
from eda_qa.utils.projects import wait_for_project_import


@pytest.fixture
def new_project(teardown_projects):
    """
    Fixture to create a new project with teardown
    """
    response = api_client.projects.create()

    project = wait_for_project_import(response.data.id).data

    teardown_projects(project)
    return project


@pytest.fixture
def teardown_projects():
    """
    Deletes projects
    """
    projects = []
    yield projects.append
    for project in projects:
        if not hasattr(project, "id"):
            continue
        api_client.projects.delete(project.id)


@pytest.fixture(scope="session")
def default_project_rulesets():
    """
    Returns a list of all unserialized rulesets in the default project repository
    """
    files = ["rulebooks/ci-cd-rules.yml", "rulebooks/local-test-rules.yml"]
    project_rulesets = []

    for file in files:
        data = yaml.safe_load(get_project_file(file))
        for ruleset in data:
            # add the filename to be used in data verification
            ruleset["filename"] = file
            project_rulesets.append(ruleset)

    return project_rulesets


@pytest.fixture(scope="session")
def default_project_rules(default_project_rulesets):
    """
    Returns a list of all unserialized rules in the default project repository
    """
    rules = []
    for ruleset in default_project_rulesets:
        for rule in ruleset["rules"]:
            # add ruleset and rulebook name (the filename) to be used in data verification
            rule["ruleset"] = ruleset["name"]
            rule["rulebook"] = ruleset["filename"]
            rules.append(rule)
    return rules


@pytest.fixture
def factory_new_project_batch(teardown_projects):
    """
    Factory to create a batch of projects with teardown
    """

    def _new_project_batch(prefix: str = "QE-batch", project_url: str = None, batch_size: int = 3):
        projects = []
        for _ in range(batch_size):
            payload = {
                "name": f"{prefix}-{nanoid.generate(alphabet='0123456abcdefg')}_project",
                "description": "Test batch project created by QE",
                "url": f"{project_url}" if project_url else None,
            }
            response = api_client.projects.create(**payload)
            project = wait_for_project_import(response.data.id).data
            projects.append(project)
            teardown_projects(project)

        return projects

    return _new_project_batch
