#!/usr/bin/env bash

if [ -z "$1" ]; then
	rsync /home/nnazirid/workspace/prep2/ preptest:/home/prep2/ -rP
fi

if [ "update" = "$1" ]; then
	rsync /home/nnazirid/workspace/prep2/ preptest:/home/prep2/ -rPu
else
	echo "Usage:\n\t$0 update"
fi
