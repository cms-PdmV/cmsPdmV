#!/bin/bash

IFS=$'\n'

echo 'Killing all main.py'
for x in $(ps -e -f | grep main | grep python | grep $USER); do
   echo "Will kill $x"
   kill -9 `echo $x | awk {'print $2'}`
done

echo 'Killing all start_mcm.sh'
for x in $(ps -e -f | grep start_mcm.sh | grep bash | grep $USER); do
   echo "Will kill $x"
   kill -9 `echo $x | awk {'print $2'}`
done

echo 'Killing all kinit.sh'
for x in $(ps -e -f | grep kinit.sh | grep bash | grep $USER); do
   echo "Will kill $x"
   kill -9 `echo $x | awk {'print $2'}`
done

unset IFS
