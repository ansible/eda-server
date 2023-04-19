#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

SCRIPTS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR="${SCRIPTS_DIR}/.."

CMD=${1:-help}
VERSION=${2:-'latest'}

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

usage() {
    log-info "Usage: $(basename "$0") <command> [command_arg]"
    log-info ""
    log-info "commands:"
    log-info "\t build-ui-image <version>     build eda-ui docker image"
    log-info "\t start-ui-image <version>     start eda-ui docker image"
    log-info "\t stop-ui-image <version>      stop eda-ui docker image"
    log-info "\t help                         show usage"
}

help() {
    usage
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
  log-debug "docker image build . -t ${_image} -f tools/docker/nginx/Dockerfile"
  docker build . -t "${_image}" -f tools/docker/nginx/Dockerfile
  rm -rf "${_temp_dir}"
}

stop-eda-ui-image() {
  local _image="eda-ui:${1}"

  if docker container ls |grep -q "${_image}"; then
    docker stop -q "${_image}"
    docker rm -q "${_image}"
  fi
}

start-eda-ui-image() {
  local _image="eda-ui:${1}"

  if docker network ls |grep -q eda_default; then
    log-err "eda-api must be running before you can start the eda-ui"
    exit 1
  fi

  stop-eda-ui-image "${1}"
  docker run --network=eda_default -d --name eda-ui -p 8080:8080 eda-ui
}

#
# execute
#
case ${CMD} in
  "build-ui-image") build-eda-ui-image "${VERSION}" ;;
  "stop-ui-image") stop-eda-ui-image "${VERSION}" ;;
  "start-ui-image") start-eda-ui-image "${VERSION}" ;;
  "help") usage ;;
   *) usage ;;
esac
