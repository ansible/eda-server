Overview
--------

This is a ansible based project to deploy all eda-server related components.

Pre-requisites
--------------

Minikube - https://minikube.sigs.k8s.io/docs ( `minikube addons enable ingress`, `minikube addons enable storage-provisioner` and `minikube addons enable default-storageclass` )

Red Hat OpenShift Local - https://developers.redhat.com/products/openshift-local/overview

Ansible - https://github.com/ansible/ansible

Kubernetes Collection for Ansible - `ansible-galaxy collection install kubernetes.core`


Usage
--------------

Make sure that your Minikube or Openshift Local is running.

After that, review the variables and make any necessary customizations. This can be done in the file:

```bash
group_vars/all/vars.yml
 ```

The following variables can be customized to determine whether a specific action is executed or not.

**env_type**: This variable supports `"minikube"` or `"openshift"` as the execution target.

**eda_deploy_operator**: This variable must be set to `"true"` for the eda-server-operator to be installed.

**eda_deploy_server**: This variable must be set to `"true"` for eda-server to be installed. At this moment, this installation still relies on the eda-server-operator, as everything is based on the "eda" crd.

**awx_deploy_operator**: This variable must be set to `"true"` for the awx-server-operator to be installed.

**awx_deploy_server**: This variable must be set to `"true"` for awx-server to be installed. At this moment, this installation still relies on the awx-server-operator, as everything is based on the "awx" crd.

To run, simply be in the same directory as the `playbook.yaml` file and execute the command: `ansible-playbook playbook.yaml`

At the end of the execution, you should have all components installed in the namespace defined in the variable `eda_namespace`

In openshift-local (crc) you can access the UI at `eda-aap-eda.apps-crc.testing` and in minikube at `eda.local`