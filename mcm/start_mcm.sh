#!/usr/bin/env bash

source kinit.sh &

echo "Running grunt"
node_modules/grunt/bin/grunt
echo "Started on: " `date`

# start Flask
python main.py