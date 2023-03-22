# Development guide

## Api tests

In most cases, to write a test for the API you will need to import `api_client` in order to make requests:

```python
from eda_qa.api import api_client
def test_something():
    response = api_client.current_user.read()
    assert response.status_code == 200
```

```python
from eda_qa.api import api_client
def test_something(create_five_projects):
    response = api_client.projects.list()
    assert len(response.data) == 5
```

By default, it uses the `default_user` defined in settings.yml. You can use the constructor to instantiate the client with a different user:

```python
from eda_qa.api import get_api_client
def test_something():
    api_client = get_api_client(user_profile="qa")
    response = api_client.current_user.read()
    assert response.status_code == 200
```

The api client wraps and override the openapi client to provide a convenient api in an extensible way.
