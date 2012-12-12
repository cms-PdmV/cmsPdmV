#!/usr/bin/env bash

#########################################################################################################################
#                                                                                                                       #
# this script resets the prep2 CouchDB database and refills with given data.                                            #
# It needs the new data in the form <data_dir>/<db_name>/<individual_id_1>, <data_dir>/<db_name>/<individual_id_2>, ... #
# where <individual_id_X> is a json with each database's document contents.                                             #
#                                                                                                                       #
# Also, it can create a design document for views. It needs a view directory in which,                                  # 
# views for each database exists in the form of <view_dir>/<db_name>_all.json                                           #
#                                                                                                                       #
#########################################################################################################################

# globals
couchhost=localhost:5984
dblist="requests chained_requests campaigns chained_campaigns flows actions users"
viewdir=/home/prep2/views
datadir=/home/prep2/maintenance/reset/data

# inform
echo "CouchDB dwells on '$couchhost'"
echo "Reseting databases: '$dblist'"

if ! [ -e $viewdir ]; then
	echo "WARNING: Could not find view directory '$viewdir'. Will not build view documents and indices."
else
	echo "Using view specification from '$viewdir'"
fi

if ! [ -e $datadir ]; then
	echo "WARNING: Could not find data directory '$datadir'. Will not fill the databases."
else
	echo "Using data from '$datadir'"
fi

# iterate through all given databases and reset each one
for db in $dblist
do
	echo 
	echo "### ### ###"
	echo

	# delete database
	echo "Deleting '$db'"
	curl -X DELETE $couchhost/$db

	# re-create database
	echo "Creating '$db'"
	curl -X PUT $couchhost/$db

	# fill database
	if [ -e $datadir ]; then
		# if dedicated directory exists
		if [ -e $datadir/$db ]; then
			echo "Filling database '$db' with data from '$datadir/$db'"
			for fname in `ls $datadir/$db`
			do
				curl -X PUT -H "Accept: application/json" $couchhost/$db/$fname --data-binary @$datadir/$db/$fname
			done
		fi
	fi

	# create design document for views
	if [ -e $viewdir ]; then
		# if dedicated view file exists
		if [ -e $viewdir/$db"_all.json" ]; then
			echo "Creating design document '$couchhost/$db/_design/$db'"
			curl -X PUT -H "Accept: application/json" $couchhost/$db/_design/$db --data-binary @$viewdir/$db"_all.json"

			# build view index
			echo "Building view index"
			curl -X GET $couchhost/$db/_design/$db/_view/all
		fi
	fi

	echo "Database '$db' has been successfully reset"
done
