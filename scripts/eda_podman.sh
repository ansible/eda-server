#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

SCRIPTS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR="${SCRIPTS_DIR}/.."

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
    log-info "\t start      startup Podman"
    log-info "\t stop       stop Podman"
    log-info "\t restart    restart Podman"
    log-info "\t tunnel     tunnel if docker is installed"
    log-info "\t help       show usage"
}

help() {
    usage
}

if podman system connection list |grep "default" &> /dev/null; then
  export PODMAN_PORT=$(podman system connection ls --format {{.URI}} | awk -F":|/" '{print $5}'|head -n 1)
  export PODMAN_UID=$(podman info | grep podman.sock | awk -F":|/" '{print $5}')
  export EDA_HOST_PODMAN_SOCKET_URL="/run/user/${PODMAN_UID}/podman/podman.sock"
  alias docker=podman
fi

start() {
  if podman machine list --format {{.LastUp}} |grep "Currently running" &> /dev/null; then
    log-info "Podman VM already running..."
    podman machine list
    return
  fi

  log-info "Starting Podman..."
  log-debug "podman machine init --cpus 2 --memory 2048 --disk-size 100 --now"
  podman machine init --cpus 2 --memory 2048 --disk-size 100 --now
  log-debug "alias docker=podman"
  alias docker=podman
  log-info "Started Podman..."
  podman machine ls
}

stop() {
  if podman machine list --format {{.LastUp}} |grep "Currently running" &> /dev/null; then
    log-info "Stopping Podman..."
    log-debug "podman machine stop"
    podman machine stop
    log-debug "podman machine rm -f"
    podman machine rm -f
    return
  fi

  log-info "Podman VM not running..."
}

restart() {
  log-info "Restarting Podman..."
  stop
  start
}

tunnel() {
  if podman machine list --format {{.LastUp}} |grep "Currently running" &> /dev/null; then
    if pgrep -fil "ssh://core@localhost:${PODMAN_PORT}" &> /dev/null; then
      log-info "podman tunnel already running"
      pgrep -fil "ssh://core@localhost:${PODMAN_PORT}"
      return
    fi

    log-info "Starting Podman tunnel..."
    log-info "PODMAN_UID=${PODMAN_UID}"
    log-info "PODMAN_UID=${PODMAN_PORT}"
    log-info "EDA_HOST_PODMAN_SOCKET_URL=${EDA_HOST_PODMAN_SOCKET_URL}"

    log-debug "sh -fnNT -L/tmp/podman.sock:/run/user/${PODMAN_UID}/podman/podman.sock -i ~/.ssh/podman-machine-default ssh://core@localhost:${PODMAN_PORT} -o StreamLocalBindUnlink=yes"
    ssh -fnNT -L/tmp/podman.sock:/run/user/"${PODMAN_UID}"/podman/podman.sock -i ~/.ssh/podman-machine-default ssh://core@localhost:"${PODMAN_PORT}" -o StreamLocalBindUnlink=yes
    log-debug "export DOCKER_HOST=unix:///tmp/podman.sock"
    export DOCKER_HOST=unix:///tmp/podman.sock
    return
  fi
  log-info "Unable to start Podman tunnel, please start podman VM first."
}

#
# execute
#
INPUT_CMD="${1:-help}"
CMD=$(echo "${INPUT_CMD}" | tr '[:upper:]' '[:lower:]':-help)
case ${CMD} in
  "start") start ;;
  "stop") stop ;;
  "tunnel") tunnel ;;
  "restart") restart ;;
  "help") usage ;;
   *) usage ;;
esac
