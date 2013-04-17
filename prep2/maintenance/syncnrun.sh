#!/usr/bin/env bash

local_workspace=/home/nnazirid/workspace/prep2/
remote_workspace=/home/prep2/
remote_machine=testy
remote_username=nnazirid

# rsync the remote workspace
rsync $local_workspace $remote_machine:$remote_workspace -rP

# restart apache instance
ssh -t $remote_username@$remote_machine sudo sh $remote_workspace/start_prep2.sh
