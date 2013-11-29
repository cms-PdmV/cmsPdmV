#!/usr/bin/env bash

# get a continuous afs token
source kinit.sh &

# kill existing
kill -9 `ps -e -f  | grep main | grep python | awk '{print $2}'`

# start CherryPy
python2.6 main.py
