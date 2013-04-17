#!/usr/bin/env bash

# this script accepts a <username> and a <role> and registers
# the username to the user database

username=$1
role=$2

# globals
default=user
couch=localhost:5984
userdb=users

if [ -z "$username" ]; then
        echo "ERROR: Bad arguments. No 'username' given."
        exit -1
fi

if [ -z "$role" ]; then
        echo "WARNING: No role given. Using default '$default'."
        role=$default
fi

exists=`curl -X GET "$couch/$userdb/$username"`

if [ -z "`echo $exists | grep error`" ]; then
	echo "Updating user '$username'..."
	revision=`echo "$exists" | cut -d',' -f2 | cut -d':' -f2 | cut -d'"' -f2`
	previous_roles=`echo "$exists" | cut -d'[' -f2 | cut -d']' -f1`
	roles="$previous_roles,\"$role\""
	curl -X PUT "$couch/$userdb/$username" -d\{\"_id\":\"$username\",\"_rev\":\"$revision\",\"username\":\"$username\",\"roles\":[$roles]\}
else
	echo "Adding user '$username'..."
	curl -X PUT "$couch/$userdb/$username" -d\{\"_id\":\"$username\",\"username\":\"$username\",\"roles\":[\"$role\"]\}
fi
