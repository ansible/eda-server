#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

SCRIPTS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR="${SCRIPTS_DIR}/.."

CMD=${1:-help}
VERSION=${2:-'latest'}
PORT=${2:-''}

# dev environment variables
export EDA_DEV_UI_GIT_REPO=${EDA_DEV_UI_GIT_REPO:-'git@github.com:ansible/ansible-ui.git'}
export EDA_DEV_UI_BRANCH=${EDA_DEV_UI_BRANCH:-'main'}

export DEBUG=${DEBUG:-false}

# import common & logging
source "${SCRIPTS_DIR}"/common/logging.sh
source "${SCRIPTS_DIR}"/common/utils.sh

trap handle_errors ERR

handle_errors() {
  log-err "An error occurred on or around line ${BASH_LINENO[0]}. Unable to continue."
  exit 1
}

# deployment dir
DEPLOY_DIR="${PROJECT_DIR}"/tools/deploy

# minikube namespace
NAMESPACE=${NAMESPACE:-aap-eda}

usage() {
    log-info "Usage: $(basename "$0") <command> [command_arg]"
    log-info ""
    log-info "commands:"
    log-info "\t build <version>              build and push image to minikube"
    log-info "\t deploy <version>             build deployment and deploy to minikube"
    log-info "\t clean                        remove deployment directory and all EDA resource from minikube"
    log-info "\t port-forward-api             forward local port to EDA API (default: 8000)"
    log-info "\t port-forward-ui              forward local port to EDA UI (default: 8080)"
    log-info "\t port-forward-pg              forward local port to Postgres (default: 5432)"
    log-info "\t eda-logs                     stream logs for all container in eda application"
    log-info "\t help                         show usage"
}

help() {
    usage
}

build-deployment() {
  local _api_image="aap-eda:${1}"
  local _ui_image="eda-ui:${1}"
  local _temp_dir="${DEPLOY_DIR}"/temp

  log-info "Using Deployment Directory: ${DEPLOY_DIR}/temp"

  if [ -d "${_temp_dir}" ]; then
    rm -rf "${_temp_dir}"
  fi
  mkdir "${_temp_dir}"

  cd "${DEPLOY_DIR}"/eda-api
  log-debug "kustomize edit set image aap-eda=${_api_image}"
  kustomize edit set image aap-eda="${_api_image}"

  cd "${DEPLOY_DIR}"/eda-ui
  log-debug "kustomize edit set image eda-ui=${_ui_image}"
  kustomize edit set image eda-ui="${_ui_image}"

  cd "${PROJECT_DIR}"
  log-debug "kustomize build ${DEPLOY_DIR} -o ${DEPLOY_DIR}/temp"
  kustomize build "${DEPLOY_DIR}" -o "${DEPLOY_DIR}/temp"
}

build-deployment-api() {
  local _api_image="aap-eda:${1}"
  local _temp_dir="${DEPLOY_DIR}"/temp

  log-info "Using Deployment Directory: ${DEPLOY_DIR}/temp"

  cd "${DEPLOY_DIR}"/eda-api
  log-debug "kustomize edit set image aap-eda=${_api_image}"
  kustomize edit set image aap-eda="${_api_image}"

  cd "${PROJECT_DIR}"
  log-debug "kustomize build ${DEPLOY_DIR} -o ${DEPLOY_DIR}/temp"
  kustomize build "${DEPLOY_DIR}" -o "${DEPLOY_DIR}/temp"
}

build-eda-api-image() {
  local _image="aap-eda:${1}"

  log-info "Building aap-eda image"
  log-debug "minikube image build . -t ${_image} -f tools/docker/Dockerfile"
  minikube image build . -t "${_image}" -f tools/docker/Dockerfile
}

build-eda-ui-image() {
  local _image="eda-ui:${1}"
  local _temp_dir=./tmp

  if [ -d "${_temp_dir}" ]; then
    rm -rf "${_temp_dir}"
  fi
  mkdir "${_temp_dir}"

  log-info "Clone ansible-ui"
  log-debug "git clone -b ${EDA_DEV_UI_BRANCH} ${EDA_DEV_UI_GIT_REPO} ${_temp_dir}/ansible-ui"
  git clone -b "${EDA_DEV_UI_BRANCH}" "${EDA_DEV_UI_GIT_REPO}" "${_temp_dir}"/ansible-ui

  log-info "Build eda-ui image"
  log-debug "minikube image build . -t ${_image} -f tools/docker/nginx/Dockerfile"
  minikube image build . -t "${_image}" -f tools/docker/nginx/Dockerfile
  rm -rf "${_temp_dir}"
}

build-all() {
  build-eda-api-image "${1}"
  build-eda-ui-image "${1}"
  build-deployment "${1}"
}

build-api() {
  build-eda-api-image "${1}"
  build-deployment-api "${1}"
}

remove-image() {
  local _image_name="${1}"

  if minikube image ls | grep "${_image_name}" &> /dev/null; then
    log-info "Removing image ${_image_name} from minikube registry"
    log-debug "minikube image rm ${_image_name}"
    minikube image rm "${_image_name}"
  fi
}

remove-deployment-tempdir() {
  if [ -d "${DEPLOY_DIR}"/temp ]; then
    log-debug "rm -rf ${DEPLOY_DIR}/temp"
    rm -rf "${DEPLOY_DIR}"/temp
  else
    log-debug "${DEPLOY_DIR}/temp does not exist"
  fi
}

deploy() {
  local _image="${1}"

  if [ -d "${DEPLOY_DIR}"/temp ]; then
    if ! kubectl get ns -o jsonpath='{..name}'| grep "${NAMESPACE}" &> /dev/null; then
      log-debug "kubectl create namespace ${NAMESPACE}"
      kubectl create namespace "${NAMESPACE}"
    fi

    kubectl config set-context --current --namespace="${NAMESPACE}"

    log-info "deploying eda to ${NAMESPACE}"
    log-debug "kubectl apply -f ${DEPLOY_DIR}/temp"
    kubectl apply -f "${DEPLOY_DIR}"/temp

  else
    log-err "You must run 'minikube:build' before running minikube:deploy"
  fi
}

clean-deployment() {
  log-info "cleaning minikube deployment..."
  if kubectl get ns -o jsonpath='{..name}'| grep "${NAMESPACE}" &> /dev/null; then
    log-debug "kubectl delete all -l 'app in (eda)' -n ${NAMESPACE}"
    kubectl delete all -l 'app in (eda)' -n "${NAMESPACE}"

    log-debug "kubectl delete pvc --all --grace-period=0 --force -n ${NAMESPACE}"
    kubectl delete pvc --all --grace-period=0 --force -n "${NAMESPACE}"
    log-debug "kubectl delete pv --all --grace-period=0 --force -n ${NAMESPACE}"
    kubectl delete pv --all --grace-period=0 --force -n "${NAMESPACE}"

    log-debug "kubectl delete role -n ${NAMESPACE} -l app=eda"
    kubectl delete role -n "${NAMESPACE}" -l app=eda
    log-debug "kubectl delete rolebinding -n ${NAMESPACE} -l app=eda"
    kubectl delete rolebinding -n "${NAMESPACE}" -l app=eda
    log-debug "kubectl delete serviceaccount -n ${NAMESPACE} -l app=eda"
    kubectl delete serviceaccount -n "${NAMESPACE}" -l app=eda

    log-debug "kubectl delete configmap -n ${NAMESPACE} -l app=eda"
    kubectl delete configmap -n "${NAMESPACE}" -l app=eda
  else
    log-debug "${NAMESPACE} does not exist"
  fi

  for image in  redis:7 postgres:13 aap-eda:latest eda-ui:latest; do
    remove-image "${image}"
  done

  remove-deployment-tempdir
}

clean-api-deployment() {
  log-info "cleaning minikube api deployment..."
  if kubectl get ns -o jsonpath='{..name}'| grep "${NAMESPACE}" &> /dev/null; then
    log-debug "kubectl delete pods -l 'comp in (worker, api, scheduler)' -n ${NAMESPACE}"
    kubectl delete pods -l 'comp in (worker, api, scheduler)' -n "${NAMESPACE}"
  fi
}

port-forward() {
  local _svc_name=${1}
  local _local_port=${2}
  local _svc_port=${3}

  log-info "kubectl port-forward svc/${_svc_name} ${_local_port}:${_svc_port} -n ${NAMESPACE}"
  kubectl port-forward "svc/${_svc_name}" "${_local_port}":"${_svc_port}" -n "${NAMESPACE}"
}

port-forward-ui() {
  local _local_port=${PORT:-"8080"}
  local _svc_name=eda-ui
  local _svc_port=8080

  log-debug "port-forward ${_svc_name} ${_local_port} ${_svc_port}"
  port-forward "${_svc_name}" "${_local_port}" "${_svc_port}"
}

port-forward-api() {
  local _local_port=${PORT:-"8000"}
  local _svc_name=eda-api
  local _svc_port=8000

  log-debug "port-forward ${_svc_name} ${_local_port} ${_svc_port}"
  port-forward "${_svc_name}" "${_local_port}" "${_svc_port}"
}

port-forward-pg() {
  local _local_port=${1}
  local _svc_name=eda-postgres
  local _svc_port=5432

  log-debug "port-forward ${_svc_name} ${_local_port} ${_svc_port}"
  port-forward "${_svc_name}" "${_local_port}" "${_svc_port}"
}


get-eda-logs() {
  log-debug "kubectl logs -n ${NAMESPACE} -l app=eda -f"
  kubectl logs -n "${NAMESPACE}" -l app=eda -f
}

#
# execute
#
case ${CMD} in
  "build") build-all "${VERSION}" ;;
  "build-api") build-api "${VERSION}" ;;
  "clean") clean-deployment "${VERSION}";;
  "clean-api") clean-api-deployment "${VERSION}";;
  "deploy") deploy "${VERSION}" ;;
  "port-forward-api") port-forward-api ${PORT} ;;
  "port-forward-ui") port-forward-ui ${PORT} ;;
  "port-forward-pg") port-forward-pg 5432 ;;
  "eda-logs") get-eda-logs ;;
  "help") usage ;;
   *) usage ;;
esac
