# Contributing

## Development environment setup

### Prerequisites

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/) or [Podman](https://podman.io/)
* [Docker Compose plugin](https://docs.docker.com/compose/) or `docker-compose` python package.
* [Poetry](https://python-poetry.org/)
* [Taskfile](https://taskfile.dev/)
* [pre-commit](https://pre-commit.com/)

For running services locally:
* Python >= 3.9

For standalone development tools written Python, like `pre-commit`,
we recommend using your system package manager,
[pipx](https://pypa.github.io/pipx/) tool or pip user install mode (`pip install --user`),
in order of preference from high to low.

#### Docker

You'll need to install Docker or Podman.

On Linux docker is generally available in your Linux distribution repositories or in 
the repositories, provided by Docker. Follow the installation instructions:
[Docker Engine installation overview](https://docs.docker.com/engine/install/).

If you're installing Docker from the official Docker's repositories, follow
[Install using the repository](https://docs.docker.com/compose/install/linux/#install-using-the-repository)
to install the Docker Compose plugin from the same repository as well.

For macOS and Windows, we recommend [Docker for Mac](https://www.docker.com/docker-mac)
and [Docker for Windows](https://www.docker.com/docker-windows) respectively.

#### Podman

On Linux podman can be installed by your Linux distribution package manager.
See [Installing on Linux](https://podman.io/getting-started/installation#installing-on-linux).

On macOS podman is available via Homebrew. 
See [Installing on macOS](https://podman.io/getting-started/installation#macos)

A new Docker Compose plugin written in Go that is installed with Docker Desktop or
from the official Docker's repositories is not compatible with podman. 
Install older version of docker-compose written in python.

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
export DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock
```

Ensure the `podman.socket` service is enabled and running:
```shell
systemctl --user enable --now podman.socket
```

#### Poetry

On Linux and macOS Poetry can be installed with the official installer:

```shell
curl -sSL https://install.python-poetry.org | python3 -
```

Alternatively you can install it with manually with `pip` or `pipx`:

```shell
pip install --user poetry
# OR
pipx install poetry
```

In ArchLinux Poetry is available in official distribution repositories:

```shell
sudo pacman -S python-poetry 
```

In macOS Poetry can be installed with Homebrew:

```shell
brew install poetry
```

#### Taskfile

Follow the [Installation](https://taskfile.dev/installation/) instruction to install Taskfile.

**Note:** For Macs with the M1 or M2 chip make sure you 
[download](https://github.com/go-task/task/releases) Task for the `arm64` architecture.

#### Pre-commit (optional)

Install [pre-commit](https://pre-commit.com/) tool.

On macOS install it with homebrew:

```shell
brew install pre-commit
```

On Linux use `pipx` or `pip install --user`:

```shell
pipx install pre-commit
# OR
pip install --user pre-commit
```

On Arch Linux:
```shell
pacman -S python-pre-commit
```

### Backend Development

#### Clone the repository

```shell
git clone git@github.com:ansible/aap-eda.git
```

#### Install dependencies

Go you project directory and install dependencies for local development:

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

#### Running services

AAP EDA requires some services like database to be running. We recommend running such services
in containerized environment (e.g. docker \ podman \ minikube \ etc.).

If you use docker or podman, you can start them with:

```shell
task docker:up:postgres
```

This will start PostgreSQL service and create a database.

If you need to run local or standalone external instance of PostgreSQL service, you will need
to create a database for EDA. By default, the database is named `eda`.

You can customize database name, it's location and access credentials with the following
environment variables:

* `EDA_DB_HOST` – Database hostname (default: `127.0.0.1`)
* `EDA_DB_PORT` – Database port (default: `5432`)
* `EDA_DB_USER` – Database username (default: `postgres`)
* `EDA_DB_PASSWORD` – Database user password (default: `secret`, only in development mode)
* `EDA_DB_NAME` – Database name (default: `eda`)

#### Executing migrations

Locally:

```task
task manage -- migrate
```

With docker compose:

```shell
task docker:migrate
```

#### Starting API server

Locally:

```task
task manage -- runserver
```

With docker compose:

```shell
task docker -- up -d api
```

Or you can start all services with docker compose at once:

```shell
task docker:up
```

#### Running tests

Locally:

```
task test
```

With docker compose:

```shell
task docker -- run api --rm python -m pytest 
```

#### Running linters

The project uses `flake8` with set of plugins, `black`, `isort` and `ruff` (experimental)
for automated code quality checks. Generally you should have `pre-commit` hook already installed,
so that linters will be executed on every commit automatically.
If needed you can run linters manually (all at once):

```shell
task lint
```

Or individual linter:
```shell
task lint:flake8
task lint:black
task lint:isort
task lint:ruff
```

#### Code formatting

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
