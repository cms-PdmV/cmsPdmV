#!/usr/bin/env bash

echo "Running grunt"
node_modules/grunt/bin/grunt
echo "Started on: " `date`

# start Flask
python3 main.py --debug
