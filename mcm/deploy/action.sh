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

# Sample data URL
if [ -z "$MCM_EXAMPLE_DATA_URL" ]; then
    echo 'Set $MCM_EXAMPLE_DATA_URL with the URL for downloading the McM data'
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
    if ! docker compose -f $REPO_PATH/deploy/mcm-components.yml up -d; then
        echo 'Unable to deploy the required components, aborting...'
        exit 1
    fi 

    echo "Waiting for $SECONDS_TO_WAIT seconds...."
    sleep $SECONDS_TO_WAIT
    docker ps -a

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

    if ! docker compose -f $REPO_PATH/deploy/mcm-components.yml down; then
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