#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

SCRIPTS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

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
    if ! command -v poetry &>/dev/null; then
        log-warn "poetry is not installed, please install poetry(version >= 1.4.0) first."
        exit 1
    fi

    log-debug "poetry run /usr/bin/env src/aap_eda/manage.py createsuperuser --noinput"
    local _result
    _result=$(poetry run /usr/bin/env src/aap_eda/manage.py createsuperuser --noinput 2>&1 || true)
    
    if [[ "${_result}" =~ "username is already taken" ]]; then
        log-info "username ${DJANGO_SUPERUSER_USERNAME} is already taken"
        exit 0
    elif [[ "${_result}" =~ "Superuser created successfully" ]]; then
        log-info "Superuser created"
        log-info "\t User: ${DJANGO_SUPERUSER_USERNAME}"
        log-info "\t Password: ${DJANGO_SUPERUSER_PASSWORD}"
        log-info "\t Email: ${DJANGO_SUPERUSER_EMAIL}"
        exit 0
    else
        log-err "${_result}"
        exit 1
    fi
}

#
# args check
#
export DJANGO_SUPERUSER_USERNAME="admin"
export DJANGO_SUPERUSER_PASSWORD="testpass"
export DJANGO_SUPERUSER_EMAIL="admin@test.com"
export EDA_DB_HOST=${EDA_DB_HOST:-localhost}
export EDA_DB_PASSWORD=${EDA_DB_PASSWORD:-secret}

while getopts p:u:e:h opt; do
    case $opt in
        p) export DJANGO_SUPERUSER_PASSWORD=$OPTARG ;;
        u) export DJANGO_SUPERUSER_USERNAME=$OPTARG ;;
        e) export DJANGO_SUPERUSER_EMAIL=$OPTARG ;;
        h) usage ;;
        *) log-err "Invalid flag supplied"; usage; exit 2
    esac
done

shift "$(( OPTIND - 1 ))"

#
# execute
#
create_user