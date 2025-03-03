#!/bin/bash

# Allows to deploy two independent environments aimed to test
# the Python 2 and the Python 3 version separetely.
# This is intended to be executed locally for development purposes.
# Make sure to provide all the environment variables `action.sh` requires

# Retrieve the folder path
SCRIPT_DIR=$(dirname "$0")
DEPLOY_SCRIPT="${SCRIPT_DIR}/action.sh"

# Dockerfile definitions for the McM application running using Python 2 and 3
MCM_PYTHON2_DOCKERFILE=''
MCM_PYTHON3_DOCKERFILE=''

if [ -z "$MCM_PYTHON2_DOCKERFILE" ]; then
    echo 'Set $MCM_PYTHON2_DOCKERFILE with the path to the Dockerfile definition for the McM application: Python 2.'
    exit 1
fi
if [ -z "$MCM_PYTHON3_DOCKERFILE" ]; then
    echo 'Set $MCM_PYTHON3_DOCKERFILE with the path to the Dockerfile definition for the McM application: Python 3.'
    exit 1
fi

# Custom environment for Python 2
function python2_env() {
    export MCM_DOCKERFILE_PATH="${MCM_PYTHON2_DOCKERFILE}"
    export DOCKER_COMPOSE_PROJECT='python2'
    export COUCHDB_PORT='24000'
    export LUCENE_PORT='24001'
    export MCM_PORT='24002'
}

# Custom environment for Python 3
function python3_env() {
    export MCM_DOCKERFILE_PATH="${MCM_PYTHON3_DOCKERFILE}"
    export DOCKER_COMPOSE_PROJECT='python3'
    export COUCHDB_PORT='25000'
    export LUCENE_PORT='25001'
    export MCM_PORT='25002'
}

function up() {
    # Deploy the Python 2 version.
    (
        python2_env
        "${DEPLOY_SCRIPT}" --up    
    )

    # Deploy the Python 3 version.
    (
        python3_env
        "${DEPLOY_SCRIPT}" --up
    )
}

function down() {
    # Remove the Python 2 version.
    (
        python2_env
        "${DEPLOY_SCRIPT}" --down
    )

    # Remove the Python 3 version.
    (
        python3_env
        "${DEPLOY_SCRIPT}" --down
    )
}

# Execute the procedure
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --up) up;;
        --down) down;;
        *) echo "Unknown option: $1"; exit 1;;
    esac
    shift
done
