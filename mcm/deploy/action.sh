#!/bin/bash

# This is only intended to be executed by the
# GitHub Action runner.

# Sets up the environment and deploys the components
echo "Docker version $(docker version)"
echo "Docker Compose version $(docker compose version)"

# Download and decompress the required data
if [ -z "$MCM_EXAMPLE_DATA_URL" ]; then
    echo 'Set $MCM_EXAMPLE_DATA_URL with the URL for downloading the McM data'
    exit 1
fi

echo 'Downloading McM data....'
curl -s $MCM_EXAMPLE_DATA_URL | tar -xzC $HOME

echo 'Creating data folders'
DATA_PATH="$HOME/container"
mkdir -p "$DATA_PATH/lucene/data" && mkdir -p "$DATA_PATH/lucene/config"
mv $HOME/couchdb $DATA_PATH
chown -R "$(whoami):docker" $DATA_PATH && chmod -R 770 $DATA_PATH

export COUCHDB_DATA="$DATA_PATH/couchdb"
export LUCENE_DATA_PATH="$DATA_PATH/lucene/data"
export LUCENE_CONF_PATH="$DATA_PATH/lucene/config"

# Path to CouchDB Lucene config file
TO_INI_PATH='deploy/couchdb-lucene.ini'
REPO_PATH=$GITHUB_WORKSPACE/repo/mcm
cp $REPO_PATH/$TO_INI_PATH $LUCENE_CONF_PATH/

# Deployment
docker compose -f $REPO_PATH/deploy/mcm-components.yml up -d
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
