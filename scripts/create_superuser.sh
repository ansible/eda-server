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
    log-info "Usage: "
    log-info "$(basename "$0") -u <username>(default:admin) -p <password>(default:testpass) -e <email>(default: admin@test.com"
    log-info "$(basename "$0") -h (returns command usage)"
    exit 0
}

create_user() {
  local _container_name="$(docker container ls -f name=^eda-postgres --format {{.Names}} 2> /dev/null)"

  wait-for-container "${_container_name}"

  log-debug "task manage -- createsuperuser --noinput"
  if task manage -- createsuperuser --noinput &> /dev/null; then
    log-info "Superuser created"
    log-debug "\t User: ${DJANGO_SUPERUSER_USERNAME}"
    log-debug "\t Password: ${DJANGO_SUPERUSER_PASSWORD}"
    log-debug "\t Email: ${DJANGO_SUPERUSER_EMAIL}"
  else
    log-info "Superuser \'${DJANGO_SUPERUSER_USERNAME}\' Already Exists!"
  fi
}

#
# args check
#
export DJANGO_SUPERUSER_USERNAME="admin"
export DJANGO_SUPERUSER_PASSWORD="testpass"
export DJANGO_SUPERUSER_EMAIL="admin@test.com"

while getopts p:u:e:h opt; do
  case $opt in
    p) export DJANGO_SUPERUSER_PASSWORD=$OPTARG ;;
    u) export DJANGO_SUPERUSER_USERNAME=$OPTARG ;;
    e) export DJANGO_SUPERUSER_EMAIL=$OPTARG ;;
    h) usage ;;
    *) log-err "Invalid flag supplied"; exit 2
  esac
done

shift "$(( OPTIND - 1 ))"

#
# execute
#
create_user