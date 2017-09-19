#!/usr/bin/env bash

# get a continuous afs token
source kinit.sh &


# the current version
revision=`git describe --abbrev=0`
echo "running revision",$revision

export MCM_REVISION=$revision
if [ ! -r node-v8.5.0-linux-x64 ] ;
then
    echo "Nodejs was not installed locally. We are downloading it's binary"
    ##TO-DO: do we download a specific version? can we get latest?
    wget --quiet https://nodejs.org/dist/v8.5.0/node-v8.5.0-linux-x64.tar.xz
    tar -xf node-v8.5.0-linux-x64.tar.xz
    rm node-v8.5.0-linux-x64.tar.xz
    source profile
    npm install
else
    echo "Node is already installed. Sourcing profile"
    source profile
fi

echo "running grunt"
node_modules/grunt/bin/grunt
echo "started on: " `date`
# start CherryPy
python2.6 main.py
