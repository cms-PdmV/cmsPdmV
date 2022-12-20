#!/usr/bin/env bash
CRED_FILE=/home/geovanny/private/pdmvserv/credentials-mcm
while [ 1 ]; do
    grep password $CRED_FILE | cut -f2 -d: | kinit pdmvserv > /dev/null
    aklog
    sleep 120
done
