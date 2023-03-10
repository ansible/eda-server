#!/usr/bin/env bash

check_vars() {
    # Variable validation.
    #
    # Args: ($@) - 1 or many variable(s) to check
    #
    local _var_names=("$@")

    for var_name in "${_var_names[@]}"; do
        if  [[ -z "$var_name" ]]; then
          log-debug "${var_name}=${!var_name}"
        else
          log-err "Environment variable $var_name is not set! Unable to continue."
          exit 1
        fi
    done
}

wait-for-container() {
  # Wait for specific time(sec) for a container become healthy.
  #
  # Args:
  #    ($1): _container_name  - Name of the docker container to health check
  #    ($2): _timeout         - Number of seconds before timeout (default: 15 seconds)
  #
  local _container_name="${1}"
  local _heath_check=".State.Health.Status"
  local _cnt=0
  local _timeout=15

  log-info "Creating super user account..."

  log-debug "Checking for ${_container_name} container"
  log-debug "docker inspect -f {{${_heath_check}}} ${_container_name} == healthy"
  until [ "$(docker inspect -f {{${_heath_check}}} "${_container_name}" 2> /dev/null)" == "healthy" ] || [ "${_cnt}" -eq "${_timeout}" ]; do
    log-debug "Healthcheck waiting...[$((++_cnt))s]"
    sleep 1;

    if [ "${_cnt}" -eq "${_timeout}" ]; then
      log-err "timeout waiting for ${_container_name} service!"
      exit 1
    fi
  done;

  log-debug "${_container_name} is healthy"
}