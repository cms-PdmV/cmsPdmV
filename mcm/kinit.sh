#!/usr/bin/env bash

while [ 1 ]; do
    cat ~pdmvserv/private/pdmvserv.txt  | kinit pdmvserv
    aklog
    sleep 40000
done
