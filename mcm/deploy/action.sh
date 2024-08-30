#!/bin/bash

# Check Docker and Docker Compose versions
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

# Sample data URL
if [ -z "$MCM_EXAMPLE_DATA_URL" ]; then
    echo 'Set $MCM_EXAMPLE_DATA_URL with the URL for downloading the McM data'
    exit 1
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

# Set environment and context.
DATE_WITH_TIME=`date "+%Y_%m_%d_%H_%M_%S"`
TMP_FOLDER="/tmp/McM_Containers_Temporal_Data_Folder_${DATE_WITH_TIME}"
DATA_PATH="/tmp/McM_Container_Data_${DATE_WITH_TIME}"
export COUCHDB_DATA="$DATA_PATH/couchdb"
export LUCENE_DATA_PATH="$DATA_PATH/lucene/data"
export LUCENE_CONF_PATH="$DATA_PATH/lucene/config"

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

    # Create a temporal folder to download the sample data
    rm -rf "${TMP_FOLDER}" && mkdir -p "${TMP_FOLDER}"

    # Download and decompress
    echo 'Downloading McM data....'
    curl -s $MCM_EXAMPLE_DATA_URL | tar -xzC "${TMP_FOLDER}/"

    # Create a temporal folder to store the container's data
    echo 'Creating data folders'
    rm -rf "${DATA_PATH}"
    mkdir -p "$DATA_PATH/lucene/data" && mkdir -p "$DATA_PATH/lucene/config"
    mv "${TMP_FOLDER}/couchdb" $DATA_PATH

    # The following ensures local deployments and environments
    # in GitHub Actions work smoothly
    chown -R "$(whoami):docker" $DATA_PATH && chmod -R 777 $DATA_PATH

    # Path to CouchDB Lucene config file
    cp $TO_INI_PATH $LUCENE_CONF_PATH/

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
    curl -s "http://localhost:8000/restapi/users/get_role" | python3 -m json.tool
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