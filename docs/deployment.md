# Deployments

This document describes how to deploy the EDA-Controller (AKA eda-server).
Currently there are three supported ways to deploy the EDA-Controller:

* Using the eda-server-operator for k8s/ocp (recommended one)
* Using docker-compose
* Using minikube

If you are looking for a development environment, please refer to the [development](development.md) document.

## Eda-server-operator

The recommended way to deploy the EDA-Controller is using the eda-server-operator.
This operator is available in the [eda-server-operator repository](https://github.com/ansible/eda-server-operator)

Look at the [eda-server-operator documentation](https://github.com/ansible/eda-server-operator#readme) for more information.

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
git clone git@github.com:ansible/eda-server.git
```

#### Configure AWX integration

You might want to configure the AWX integration. To do so, you need to set the environment variables `EDA_CONTROLLER_URL` and `EDA_CONTROLLER_SSL_VERIFY`. For example:

```shell
  export EDA_CONTROLLER_URL=https://awx-example.com
  export EDA_CONTROLLER_SSL_VERIFY=yes
```

```shell
cd tools/docker
```

You may want to pull the latest images from the registry:

```shell
docker-compose -p eda -f docker-compose-stage.yaml pull
```

You can start all services with:

```shell
docker-compose -p eda -f docker-compose-stage.yaml up
```

Note: **You can use the environment variables `EDA_IMAGE_URL` and `EDA_UI_IMAGE_URL` to use a different image url. By default is the latest code from the main branch.**

## Deploy using Minikube and Taskfile

Minikube is the recommended method for macOS users

### Requirements

* [Kubernetes CLI (kubectl)](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
* [kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/)
* [minikube](https://minikube.sigs.k8s.io/docs/start/)
* [Taskfile](https://taskfile.dev/installation/#binary)
* bash, version 3.* or above

### Deployment steps

1. Copy environment properties example file to default location

   ```shell
   cp ./tools/deploy/environment.properties.example ./tools/deploy/environment.properties
   ```

2. Edit ./tools/deploy/environment.properties file and add your values.

3. Start minikube if it is not already running:

   ```shell
   minikube start
   ```

4. Ensure minikube instance is up and running:

   ```shell
   minikube status
   ```

5. Run the deployment:

   ```shell
   task minikube:all
   ```

6. Forward the webserver port to the localhost:

   ```shell
   task minikube:fp:ui
   ```

**Note**: For fedora, the binary may be `go-task`.

You can now access the UI at <https://localhost:8443/> using the above credentials.
