# Development environment setup

## Prerequisites

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/) or [Podman](https://podman.io/)
* [Docker Compose plugin](https://docs.docker.com/compose/) or `docker-compose` python package.
* [Poetry](https://python-poetry.org/) >= 1.4.0
* [Taskfile](https://taskfile.dev/)
* [gnupg](https://www.gnupg.org/)
* [pre-commit](https://pre-commit.com/)

For running services locally:

* Python >= 3.11

For standalone development tools written in Python, such as `pre-commit`,
we recommend using your system package manager,
[pipx](https://pypa.github.io/pipx/) tool or pip user install mode (`pip install --user`),
in decreasing order of preference.

### Docker

You'll need to install Docker or Podman.

On Linux, docker is generally available in your Linux distribution repositories or in
the repositories, provided by Docker. Follow the installation instructions:
[Docker Engine installation overview](https://docs.docker.com/engine/install/).

If you're installing Docker from the official Docker's repositories, follow
[Install using the repository](https://docs.docker.com/compose/install/linux/#install-using-the-repository)
to install the Docker Compose plugin from the same repository as well. Please note that when installing
Docker Compose via the official Docker repo, an alias or symlink for `docker-compose` is not automatically
created and you must create one manually. For example, on Fedora:

```shell
sudo ln -s /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
```

For macOS and Windows, we recommend [Docker for Mac](https://www.docker.com/docker-mac)
and [Docker for Windows](https://www.docker.com/docker-windows) respectively.

### Podman

On Linux, podman can be installed using your Linux distribution package manager.
See [Installing on Linux](https://podman.io/getting-started/installation#installing-on-linux).

On macOS, podman is available via Homebrew.
See [Installing on macOS](https://podman.io/getting-started/installation#macos)

#### Notes for linux users

A new Docker Compose plugin written in Go, which is installed with Docker Desktop or
from the official Docker's repositories, is not compatible with podman.
Instead you should use the older version of docker-compose which is written in python.

We suggest installing into a user directory with `pip install --user` or `pipx` tool:

```shell
pip install --user docker-compose
# OR
pipx install docker-compose
```

By default, all dev scripts use `docker` binary.
Podman users must install `podman-docker` package or run the following command:

```shell
sudo ln -s $(which podman) $(dirname $(which podman))/docker
```

The `DOCKER_HOST` environment variable must be defined pointing
to the podman socket to be able to use `docker-compose`. Example:

```shell
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
```

Ensure the `podman.socket` service is enabled and running:

```shell
systemctl --user enable --now podman.socket
```

### Poetry

On Linux and macOS, Poetry can be installed with the official installer:

```shell
curl -sSL https://install.python-poetry.org | python3.11 -
```

Alternatively, you can install it with manually with `pip` or `pipx`:

```shell
pip install --user poetry
# OR
pipx install poetry
```

In ArchLinux, Poetry is available in the official distribution repositories:

```shell
sudo pacman -S python-poetry
```

In macOS, Poetry can be installed with Homebrew:

```shell
brew install poetry
```

### Taskfile

Follow the [Installation](https://taskfile.dev/installation/) instructions to install Taskfile.

Depending on your OS or distribution, Taskfile will be packaged with the binary named `task`, whilst others name it `go-task`.
The instructions below assume your Taskfile binary is named `task`, but please keep in mind that the binary on your system may have a different name.

**Note:** For Macs with the M1 or M2 chip make sure you
[download](https://github.com/go-task/task/releases) Task for the `arm64` architecture.

### gnupg

Linux environments have gpg installed by default. On macOS its optional so you can install it using brew.

```shell
brew install gpg
```

### Pre-commit (optional)

Install [pre-commit](https://pre-commit.com/) tool.

On macOS, install it with homebrew:

```shell
brew install pre-commit
```

On Linux, use `pipx` or `pip install --user`:

```shell
pipx install pre-commit
# OR
pip install --user pre-commit
```

On Arch Linux:

```shell
pacman -S python-pre-commit
```

**Note:** The `poetry-lock` hook will check to ensure consistency across the poetry.lock and
pyproject.toml files. In case of conflict, a developer must manually execute either `poetry update` or
`poetry lock` to resolve it.

## Development environment steps

### Clone the repository

```shell
git clone git@github.com:ansible/eda-server.git
```

### Install dependencies

Go to your project directory and install dependencies for local development:

```shell
task dev:init
```

Or if you want to customize installation options, you may run commands, executed by the `dev:init`
target manually:

```shell
poetry install -E dev
pre-commit install
```

#### Building container images

First you need to build a container image:

```shell
task docker:build
```

This will build `localhost/aap-eda:latest` development image:

```shell
$ docker images
REPOSITORY                                    TAG         IMAGE ID       CREATED        SIZE
localhost/aap-eda                             latest      28fd94c8cf89   5 hours ago    611MB
```

To override image name:(using short git hash for version here)

```shell
export EDA_IMAGE="ansible/eda-server:$(git rev-parse --short HEAD)"; task docker:build
```

```shell
$ docker images

REPOSITORY                      TAG         IMAGE ID       CREATED          SIZE
ansible/eda-server              12146d8     51fb0c850b94   10 minutes ago   682MB
```

### Running services

AAP EDA requires some services, such as database and redis to be running. We recommend running such services
in a containerized environment (e.g. docker / podman / minikube etc.).

You can start all minimal required containers by running:

```shell
task docker:up:minimal
```

Alternately, you can start all containers, including the applications, by running:

```shell
task docker:up
```

If you use docker or podman, you can start just the postgres instance with:

```shell
task docker:up:postgres
```

### Initializing the deployment

You can initialize the deployment with some basic resources useful for development:

```shell
ansible-playbook  tools/ansible/eda_init.yml
```

### Customizing database settings

If you need to run a local or standalone external instance of PostgreSQL service, you will need
to create a database for EDA. By default, the database is named `eda`.

You can customize the database name, it's location and access credentials with the following
environment variables:

* `EDA_DB_HOST` – Database hostname (default: `127.0.0.1`)
* `EDA_DB_PORT` – Database port (default: `5432`)
* `EDA_DB_USER` – Database username (default: `postgres`)
* `EDA_DB_PASSWORD` – Database user password (default: `secret`, only in development mode)
* `EDA_DB_NAME` – Database name (default: `eda`)

### TLS-enabled redis

If you wish to run a development environment requiring TLS connections to redis it is a simple
process...

1. build your container images as described above
2. start them using `docker-compose -f ./tools/docker/docker-compose-dev-redis-tls.yaml up`

In order to successfully run the development environment tests using TLS-enabled
redis you will need to export the following environment variables:

* `EDA_MQ_CLIENT_CERT_PATH=<<workspace>>/tools/docker/redis-tls/client/client.crt`
* `EDA_MQ_CLIENT_KEY_PATH=<<workspace>>/tools/docker/redis-tls/client/client.key`
* `EDA_MQ_CLIENT_CACERT_PATH=<<workspace>>/tools/docker/redis-tls/ca.crt`

If using `podman` you will also need to export:

* `EDA_PODMAN_SOCKET_URL=tcp://0.0.0.0:8888`

`EDA_MQ_CLIENT_CERT_PATH` has special significance.  While all three `EDA_MQ_*`
variables are required `EDA_MQ_CLIENT_CERT_PATH` determines whether requests
are made to redis using TLS.  You can use this as a convenience in switching
client-side processing between TLS and non-TLS by always exporting
`EDA_MQ_CLIENT_KEY_PATH` and `EDA_MQ_CLIENT_CACERT_PATH` and switching behavior
by setting/clearing `EDA_MQ_CLIENT_CERT_PATH`.

### Executing migrations

Locally:

```shell
task manage -- migrate
```

With docker compose:

```shell
task docker:migrate
```

### Seeding the database

Locally:

```shell
task manage -- create_initial_data
```

With docker compose:

```shell
task docker -- run --rm eda-api aap-eda-manage create_initial_data
```

### Create superuser

```shell
task create:superuser
```

### Starting API server

Locally:

```shell
task run:api
# OR
task manage -- runserver
```

**NOTE**: When running the API server locally, make sure to bring up the scheduler container
by running `task run:scheduler`

With docker compose:

```shell
task docker -- up -d eda-api
```

### Running tests

To run tests locally, you need to have a running instance of postgresql and redis.

Run all tests:

```shell
task test
```

Run a single module:

```shell
task test -- tests/integration/api/test_activation.py
```

Run a single test:

```shell
task test -- tests/integration/api/test_activation.py::test_retrieve_activation
```

With docker compose:

```shell
task docker -- run --rm eda-api python3.11 -m pytest
```

### Running linters

The project uses `flake8` with a set of plugins, `black`, `isort` and `ruff` (experimental),
for automated code quality checks. Generally you should have the `pre-commit` hook already installed,
so that linters will be executed automatically on every commit.
If needed you can run linters manually (all at once):

```shell
task lint
```

Or an individual linter:

```shell
task lint:flake8
task lint:black
task lint:isort
task lint:ruff
```

### Code formatting

To automatically format your source code run:

```shell
task format
```

This will execute `isort` and `black` tools.

You can run individual formatting tools if needed:

```shell
task format:isort
task format:black
```

You can now access the api at <https://localhost:8443/api/eda/v1/docs> with the default credentials `admin`/`testpass`.
You can also access the standalone UI at <https://localhost:8443/>.
