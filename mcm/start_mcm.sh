#!/usr/bin/env bash

# Environment variables for McM
COUCH_DB_CRED=...
CERT_FILE=...
KEY_FILE=...
CRED_FILE=...

export COUCH_CRED=$COUCH_DB_CRED
export USERCRT=$CERT_FILE
export USERKEY=$KEY_FILE
export CRED_FILE=$CRED_FILE

# Host deployment
export MCM_HOST='0.0.0.0'
export MCM_PORT='8000'

function setup() {
  source kinit.sh &

  echo "Running grunt"
  node_modules/grunt/bin/grunt
  echo "Started on: " `date`
}

# Start McM server
CMD=$1
if [ "$CMD" = "dev" ]; then
  setup
  python main.py --port $MCM_PORT --host $MCM_HOST
elif [ "$CMD" = "prod" ]; then
  setup
  gunicorn wsgi:app
else
  echo "Please select a mode: dev or prod"
  exit 1
fi
