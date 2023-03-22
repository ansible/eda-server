#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR=$SCRIPT_DIR/../../
SPEC_URL=${1:-"http://localhost:8000/api/eda/v1/openapi.json"}
PROG_NAME=$(basename "$0")
GENERATOR_VERSION=6.1.0

print_error() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: $*" >&2
}

print_msg() {
    echo "$PROG_NAME - $*"
}

check_error() {
    if [[ $? -ne 0 ]]; then
        print_error "FAILED"
    fi
}

check_dependencies() {
    print_msg "Checking dependencies"
    for prog in openapi-generator jq curl pre-commit; do
        if ! command -v ${prog} &>/dev/null; then
            print_error "${prog} program could not be found. Please install it"
            exit 1
        fi
    done
    print_msg "Dependencies OK"
}

download() {
    if [[ "$SPEC_URL" =~ ^http.* ]]; then
        print_msg "Downloading the spec file as reference"
        curl -q "${SPEC_URL}" --output ./openapi.tmp &>/dev/null
        jq < ./openapi.tmp > openapi.json && rm -rf ./openapi.tmp
        print_msg "openapi spec downloaded"
    fi
}

generate() {
    print_msg "Generating library"
    OPENAPI_GENERATOR_VERSION=$GENERATOR_VERSION openapi-generator generate \
    -g python \
    -i "${SPEC_URL}" \
    -o "${PROJECT_DIR}" \
    -c "${SCRIPT_DIR}/config.yml" \
    --global-property "apiTests=false,modelTests=false"
    check_error
    print_msg "Library generated"
}

run_precommit() {
    print_msg "Running pre-commit"
    pre-commit run --all
}

check_dependencies
generate
run_precommit
download
print_msg "Done"
