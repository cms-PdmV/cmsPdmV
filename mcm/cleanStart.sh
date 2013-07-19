#!/bin/bash

kill -9 `ps -f -e | grep ./start_mcm.sh | awk '{print $2}'`
killall sleep
