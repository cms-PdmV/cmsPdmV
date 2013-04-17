#!/usr/bin/env bash

filename=$1

cern-get-sso-cookie --krb --nocertverify -u https://cms-pdmv.cern.ch/mcm -o ssocookie.txt 

curl -L -k --cookie ssocookie.txt --cookie-jar ssocookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/campaigns/save/ -H "Content-Type: application/json" -X PUT --data-binary @$filename

#curl -L -k --cookie ssocookie.txt --cookie-jar ssocookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/campaigns/delete/$filename -X DELETE

#curl -L -k --cookie ssocookie.txt --cookie-jar ssocookie.txt https://cms-pdmv-dev.cern.ch/mcm/restapi/chained_campaigns/delete/chain_$filename -X DELETE

