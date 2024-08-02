#!/usr/bin/env bash

while [ 1 ]; do
    grep password /home/mcm/private/credentials | cut -f2 -d: | kinit pdmvserv
    aklog
    sleep 120
done
