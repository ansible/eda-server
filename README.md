![Maintained? yes](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

[![codecov](https://codecov.io/gh/ansible/eda-server/graph/badge.svg?token=N6Z2DZGKGZ)](https://codecov.io/gh/ansible/eda-server)

[![GitHub Workflow Status](https://github.com/ansible/eda-server/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/ansible/eda-server/actions/workflows/ci.yaml?query=branch%3Amain)

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=ansible_eda-server&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=ansible_eda-server)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=ansible_eda-server&metric=coverage)](https://sonarcloud.io/summary/overall?id=ansible_eda-server)

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)
![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)

# Event Driven Ansible Controller

This repository contains the source code for the Event Driven Ansible Controller, aka EDA-Controller.

Licensed under [Apache Software License 2.0](LICENSE)

## How to install

Refer to the [deployment guide](docs/deployment.md) for further information if you want to install and run the application.

## Development environment

Refer to the [development guide](docs/development.md) for further information if you want to setup a development environment.

## Contributing

We ask all of our community members and contributors to adhere to the [Ansible code of conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html).
If you have questions or need assistance, please reach out to our community team at <codeofconduct@ansible.com>

Refer to the [Contributing guide](docs/contributing.md) for further information.

## Communication

See the [Communication](https://github.com/ansible/eda-server/blob/main/docs/contributing.md#communication) section of the
Contributing guide to find out how to get help and contact us.

For more information about getting in touch, see the
[Ansible communication guide](https://docs.ansible.com/ansible/devel/community/communication.html).

## OpenAPI specification

You can access the Event Driven Ansible OpenAPI specification from a
running instance:

- API docs (browser):
  - http://$HOST:$PORT/api/eda/v1/docs/
- OpenAPI JSON:
  - http://$HOST:$PORT/api/eda/v1/openapi.json

Download examples:

```bash
# Basic auth (JSON)
curl -u admin:password \
  "http://localhost:8000/api/eda/v1/openapi.json" -o eda.json

# Token auth (JSON)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/eda/v1/openapi.json" -o eda.json
```

Notes:
- For HTTPS with self-signed certificates, add `-k` to curl for local testing.
- The specification's `info.version` reflects the installed `aap-eda`
  package version on the running instance, from `pyproject.toml`.

## Credits

EDA-Controller is sponsored by [Red Hat, Inc](https://www.redhat.com).
