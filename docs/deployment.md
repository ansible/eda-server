# Deployments

This document describes how to deploy the EDA-Controller (AKA eda-server).
Currently there are three supported ways to deploy the EDA-Controller:

* Using the eda-server-operator for k8s/ocp (recommended one)
* Using docker-compose
* Using kind (Kubernetes in Docker)

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

Note: **You can use the environment variables `EDA_IMAGE_URL` and `EDA_UI_IMAGE` to use a different image url. By default is the latest code from the main branch.**

## Deploy using Kind and Taskfile

Kind is the recommended method for local Kubernetes deployments

### Requirements

* [Docker](https://www.docker.com/) or [Podman](https://podman.io/)
* [Kubernetes CLI (kubectl)](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
* [kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/)
* [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
* [Taskfile](https://taskfile.dev/installation/#binary)

### Deployment steps

1. Copy environment properties example file to default location

   ```shell
   cp ./tools/deploy/environment.properties.example ./tools/deploy/environment.properties
   ```

2. Edit ./tools/deploy/environment.properties file and add your values.

3. Create a kind cluster if one is not already running:

   ```shell
   kind create cluster
   ```

4. Ensure the kind cluster is up and running:

   ```shell
   kind get clusters
   ```

5. Run the deployment:

   ```shell
   task kind:all
   ```

6. Forward the webserver port to the localhost:

   ```shell
   task kind:fp:ui
   ```

7. Access the UI at <https://localhost:8443/> with the default credentials `admin`/`testpass`.

   You can also inspect the API documentation at <https://localhost:8443/api/eda/v1/docs>
   or navigate through the resources with the DRF browsable API at <https://localhost:8443/api/eda/v1/>.

**Note**: For fedora, the binary may be `go-task`.

**Note**: Image builds use `podman` by default. To use Docker instead, set the `CONTAINER_ENGINE` variable:

```shell
CONTAINER_ENGINE=docker task kind:all
```
