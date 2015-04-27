#!/usr/bin/env bash

while [ 1 ]; do
    grep password  /home/mcm/credentials | cut -f2 -d: | kinit pdmvserv
    ##klist  | mailx -s "kinit for pdmvserv" pdmvserv@cern.ch 
    aklog
    sleep 60
done
