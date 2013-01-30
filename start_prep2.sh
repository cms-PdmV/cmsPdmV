#!/usr/bin/env bash

username=anorkus

# check for root( root is needed to avoid SELINUX restrictions for sockets)
if ! id | grep -q "uid=0(root)" ; then
	echo "ERROR:  must be root in order to run this script"
	exit 1
fi

# get kerberos credentials
klist 
if [ $? -eq 1 ]; then
    kinit $username
    aklog
fi

# check CouchDB status
couch_status=`/etc/init.d/couchdb status | grep running`

if [ -z "$couch_status" ]; then
	echo 'WARNING: CouchDB is not running. Trying to raise an instance...'
	# fallback to raise an instance
	couch_status=`sudo /etc/init.d/couchdb start | grep OK`
	if [ -z "$couch_status" ]; then
		echo 'ERROR: Could not raise CouchDB instance. Exiting...'
		exit
	else
		echo 'INFO: CouchDB instance running!'
	fi	
fi

# spawn Apache server
apache_status=`sudo /etc/init.d/httpd restart | grep OK`
if [ -z "$couch_status" ]; then
	echo 'ERROR: Could not raise Apache instance. Exiting...'
        exit
fi
