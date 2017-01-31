#!/usr/bin/env bash

# get a continuous afs token
source kinit.sh &

# kill existing
#kill -9 `ps -e -f | grep main | grep python | awk '{print $2}'`
#kill -9 `ps -e -f | grep mcm | grep -v $$ | awk '{print $2}'`

# the current version
revision=`git describe --abbrev=0`
echo "running revision",$revision
export MCM_REVISION=$revision
echo "running grunt"
grunt
echo "started on: " `date`
# start CherryPy
python2.6 main.py
