#!/usr/bin/env bash

while [ 1 ]; do
    grep password  ~pdmvserv/private/credentials | cut -f2 -d: | kinit pdmvserv
    klist  | mailx -s "kinit for pdmvserv" pdmvserv@cern.ch 
    aklog
    sleep 40000
done
