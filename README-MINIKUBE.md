# Deploy using Minikube and Taskfile

Minikube is the recommended method for macOS users

## Requirements

- [Kubernetes CLI (kubectl)](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
- [kustomize](https://kubectl.docs.kubernetes.io/installation/kustomize/)
- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Taskfile](https://taskfile.dev/installation/#binary)
- bash, version 3.* or above

## Deployment

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