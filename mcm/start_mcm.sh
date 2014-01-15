#!/usr/bin/env bash

# get a continuous afs token
source kinit.sh &

# kill existing
kill -9 `ps -e -f | grep main | grep python | awk '{print $2}'`
kill -9 `ps -e -f | grep mcm | grep -v $$ | awk '{print $2}'`

# the current version
revision=`git reflog | grep tags/ | head -1 | cut -d '/' -f2`
echo "running revision",$revision
export MCM_REVISION=$revision

# start CherryPy
python2.6 main.py
