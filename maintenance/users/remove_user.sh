#!/usr/bin/env bash

# this script accepts a <username> and removes it from the user database

username=$1

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
        echo "Removing user '$username'..."
        revision=`echo "$exists" | cut -d',' -f2 | cut -d':' -f2 | cut -d'"' -f2`
        curl -X DELETE "$couch/$userdb/$username?rev=$revision"
else
        echo "ERROR: User '$username' does not exist."
        exit -2
fi
