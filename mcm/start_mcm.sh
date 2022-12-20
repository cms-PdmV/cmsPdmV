#!/usr/bin/env bash

# Environment variables for McM
COUCH_DB_CRED=...
CERT_FILE=...
KEY_FILE=...

export COUCH_CRED=$COUCH_DB_CRED
export USERCRT=$CERT_FILE
export USERKEY=$KEY_FILE

source kinit.sh &

echo "Running grunt"
node_modules/grunt/bin/grunt
echo "Started on: " `date`

# start Flask
python main.py