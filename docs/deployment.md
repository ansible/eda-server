# Deployments

This document describes how to deploy the EDA-Controller.
Currently there are two ways to deploy the EDA-Controller: using docker-compose or using minikube.

If you are looking for a development environment, please refer to the [development](development.md) document.

## Docker Compose

### Prerequisites

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/) or [Podman](https://podman.io/)
* [Docker Compose plugin](https://docs.docker.com/compose/) or `docker-compose` python package.
* [Taskfile](https://taskfile.dev/)

#### Docker

You'll need to install Docker or Podman.

For further information please refer our [guidelines](development.md#Docker).

#### Podman

For further information please refer our [guidelines](development.md#Podman).

#### Taskfile

For further information please refer our [guidelines](development.md#Taskfile).

### Deployment steps

#### Clone the repository

```shell
git clone git@github.com:ansible/aap-eda.git
```

#### Building container images

```shell
cd tools/docker
```

First you need to build the container image:

```shell
docker-compose -p eda -f docker-compose-stage.yaml build
```

This will build `localhost/aap-eda:latest` image:

```shell
$ docker images

REPOSITORY                                    TAG         IMAGE ID       CREATED        SIZE
localhost/aap-eda                             latest      28fd94c8cf89   5 hours ago    611MB
```

#### Running services

You can start all services with:

```shell
docker-compose -p eda -f docker-compose-stage.yaml up
```

## Deploy using Minikube and Taskfile

Minikube is the recommended method for macOS users

### Requirements

* [Kubernetes CLI (kubectl)](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
* [kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/)
* [minikube](https://minikube.sigs.k8s.io/docs/start/)
* [Taskfile](https://taskfile.dev/installation/#binary)
* bash, version 3.* or above

### Deployment steps

1. Start minikube if it is not already running:

    minikube start

2. Ensure minikube instance is up and running:

    minikube status

3. Run the deployment:

    task minikube:all

4. Forward the webserver port to the localhost:

    task minikube:fp:ui

**Note**: For fedora, the binary may be `go-task`.

You can now access the UI at <http://localhost:8080/eda/> using the above credentials.
