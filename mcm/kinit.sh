#!/usr/bin/env bash

while [ 1 ]; do
    cat ~pdmvserv/private/pdmvserv.txt  | kinit pdmvserv
    klist  | mailx -s "kinit for pdmvserv" pdmvserv@cern.ch 
    aklog
    sleep 40000
done
