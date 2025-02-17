#!/usr/bin/env bash
# Renew a Kerberos ticket for authenticating SSH sessions.

if [ -n "${MCM_GSSAPI_WITH_MIC}" ]; then 
    if [ -z "${MCM_SERVICE_ACCOUNT_USERNAME}" ]; then echo "MCM_SERVICE_ACCOUNT_USERNAME is not set. Provide the service account username"; exit 1; fi;
    if [ -z "${MCM_SERVICE_ACCOUNT_PASSWORD}" ]; then echo "MCM_SERVICE_ACCOUNT_PASSWORD is not set. Provide the service account password"; exit 1; fi;
    echo "Renewing a Kerberos ticket for user: ${MCM_SERVICE_ACCOUNT_USERNAME}"

    while [ 1 ]; do
        echo "${MCM_SERVICE_ACCOUNT_PASSWORD}" | kinit "${MCM_SERVICE_ACCOUNT_USERNAME}"
        aklog
        sleep 120
    done
fi
