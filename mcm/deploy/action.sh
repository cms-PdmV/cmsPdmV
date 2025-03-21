#!/bin/bash

if ! docker version; then
    echo 'Docker is not available, install it and start it before running this'
    exit 1
fi
if ! docker compose version; then
    echo 'Docker Compose is not available, install it and start it before running this'
    exit 1
fi

# Optional: Project name for the Docker Compose deployment
# If not provided, set it to 'default'
if [ -z "$DOCKER_COMPOSE_PROJECT" ]; then
    DOCKER_COMPOSE_PROJECT='default'
fi

# Sample data
if [ -z "$MCM_EXAMPLE_DATA_PATH" ]; then
    if [ -z "$MCM_EXAMPLE_DATA_URL" ]; then
        echo 'Set $MCM_EXAMPLE_DATA_PATH with the path to the compressed database dump'
        echo 'or'
        echo 'Set $MCM_EXAMPLE_DATA_URL with the URL for downloading it'
        exit 1
    fi
fi

# Path (or URL) pointing to the Dockerfile definition for the McM application.
if [ -z "$MCM_DOCKERFILE_PATH" ]; then
    echo 'Set $MCM_DOCKERFILE_PATH with the path or url pointing to the Dockerfile definition for the McM application'
    exit 1
fi

# Path to the McM source code
if [ -z "$REPO_PATH" ]; then
    echo 'Set $REPO_PATH with the absolute path to the McM source code including the mcm/ internal folder'
    exit 1
fi

# Path to `couchdb-lucene.ini` required to set
# this setting for the CouchDB Lucene component
if [ -z "$TO_INI_PATH" ]; then
    echo 'Set $TO_INI_PATH with the absolute path to the file `couchdb-lucene.ini` available in the repository for the execution environment'
    exit 1
fi

# Check the certificate and key file for authenticating CMS Web services is provided.
if [ -z "$CMSWEB_CERTIFICATE_FILE" ]; then
    echo 'Set $CMSWEB_CERTIFICATE_FILE with the path to the users certificate file'
    exit 1
fi

if [ -z "$CMSWEB_KEY_FILE" ]; then
    echo 'Set $CMSWEB_KEY_FILE with the path to the users certificate key file'
    exit 1
fi

# McM application port.
if [ -z "$MCM_PORT" ]; then
    echo 'Application port not provided. Set it via $MCM_PORT'
    exit 1
fi

# Credentials for opening a SSH session for performing submissions
if [ -z "$MCM_SERVICE_ACCOUNT_USERNAME" ]; then
    echo 'Service account username not provided, using a placeholder...'
    MCM_SERVICE_ACCOUNT_USERNAME='notexists'
fi

if [ -z "$MCM_SERVICE_ACCOUNT_PASSWORD" ]; then
    echo 'Service account password not provided, using a placeholder...'
    MCM_SERVICE_ACCOUNT_PASSWORD='notexists'
fi

if [ -z "$MCM_WORK_LOCATION_PATH" ]; then
    echo 'Work folder for creating artifacts not provided. Setting the default to /tmp'
    MCM_WORK_LOCATION_PATH='/tmp/'
fi

if [ -z "$MCM_EXECUTOR_HOST" ]; then
    echo 'Remote host not provided. Setting the default to localhost'
    MCM_EXECUTOR_HOST='localhost'
fi

# Set environment and context.
TMP_FOLDER=$(mktemp -d)
DATA_PATH=$(mktemp -d)
export COUCHDB_DATA="$DATA_PATH/couchdb"
export LUCENE_DATA_PATH="$DATA_PATH/lucene/data"
export LUCENE_CONF_PATH="$DATA_PATH/lucene/config"

# Set up the database dump either from a local compressed file
# or by downloading it from a URL
function prepare_database_dump() {
    if [ -n "$MCM_EXAMPLE_DATA_PATH" ]; then
        # If the local file path is provided, use it.
        echo "Decompressing file from: ${MCM_EXAMPLE_DATA_PATH}"
        tar -xzC "${TMP_FOLDER}/" -f "${MCM_EXAMPLE_DATA_PATH}" || exit
    elif [ -n "$MCM_EXAMPLE_DATA_URL" ]; then
        # Otherwise attempt to download it
        echo "Downloading file from: ${MCM_EXAMPLE_DATA_URL}"
        curl -sf "${MCM_EXAMPLE_DATA_URL}" | tar -xzC "${TMP_FOLDER}/" || exit
    else
        # This should never happen!
        echo "Unable to prepare the database dump"
        exit 1
    fi
}

# Retrieve all the logs related to the containers
# with an exit code != 0 related to the current project
function debug_containers() {
    echo ""
    exited_containers=$(docker ps -a --filter "status=exited" --filter "label=com.docker.compose.project=${DOCKER_COMPOSE_PROJECT}" --format "{{.Names}}")
    for container in $exited_containers; do
        # Get the exit code of the container
        exit_code=$(docker inspect --format='{{.State.ExitCode}}' "$container")
        exit_code_num=$((exit_code + 0))

        if [ "$exit_code_num" -ne 0 ]; then
            echo "The following container seems to be failing: $container"
            echo "Exit Code: $exit_code_num"
            echo "Logs:"
            docker logs "$container"
            echo "-----------------------------"
        fi
    done
    echo ""
}

# Start the deployment
function up() {
    echo 'Starting deployment...'

    # Prepare the database dump
    prepare_database_dump

    # Create a temporary folder to store the container's data
    echo 'Creating data folders'
    mkdir -p "$DATA_PATH/lucene/data" && mkdir -p "$DATA_PATH/lucene/config"
    mv "${TMP_FOLDER}/couchdb" $DATA_PATH

    # The following ensures local deployments and environments
    # in GitHub Actions work smoothly
    chown -R "$(whoami):docker" $DATA_PATH && chmod -R 777 $DATA_PATH

    # Path to CouchDB Lucene config file
    # Set the correct URLs of CouchDB and set the port
    cp $TO_INI_PATH $LUCENE_CONF_PATH/
    DECODED_CREDENTIAL=$(echo "${COUCH_CRED#Basic }" | base64 -d)
    FULL_LUCENE_COUCHDB_URL=$(echo "$MCM_COUCHDB_URL" | sed "s|http://|http://$DECODED_CREDENTIAL@|")
    sed -i "s#<MCM_COUCHDB_URL>#${FULL_LUCENE_COUCHDB_URL}#g" "${LUCENE_CONF_PATH}/couchdb-lucene.ini"

    # Set the McM base URL. This is required for external integrations
    # with scripts like the Injection script with the PdmV `wmcontrol`
    # module.
    export MCM_BASE_URL="http://$(hostname):${MCM_PORT}/"
    echo "McM application - Base URL: ${MCM_BASE_URL}"

    # Deployment
    if ! docker compose -f $REPO_PATH/deploy/mcm-components.yml -p $DOCKER_COMPOSE_PROJECT up -d; then
        echo 'Unable to deploy the required components, aborting...'
        exit 1
    fi 

    echo "Waiting for $SECONDS_TO_WAIT seconds...."
    sleep $SECONDS_TO_WAIT

    # Display the current status and logs if required
    docker ps -a
    debug_containers

    echo "Services status..."
    echo "CouchDB:"
    curl -s "http://localhost:$COUCHDB_PORT/" | python3 -m json.tool
    echo "CouchDB Lucene"
    curl -s "http://localhost:$LUCENE_PORT/" | python3 -m json.tool
    echo "McM application"
    curl -s "http://localhost:$MCM_PORT/restapi/users/get_role" | python3 -m json.tool
}

# Take down the deployment
function down() {
    echo 'Removing deployment...'

    if ! docker compose -f $REPO_PATH/deploy/mcm-components.yml -p $DOCKER_COMPOSE_PROJECT down; then
        echo 'Unable to remote the deployment. Stop and remove the containers manually...'
        exit 1
    fi
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
