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

# init cherrypy web server (optional: take a different path than ./) 
cherry_path=$1

if [ -z $cherry_path ]; then
	cherry_path=main.py
fi

python $cherry_path
