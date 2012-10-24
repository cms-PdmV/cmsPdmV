#!/usr/bin/env bash

# this is a script to automagically install PREP2.0 service. It needs an SLC6 environment (perhaps a CERN vm) and 
# root permissions to create the file tree, install all relevant dependencies and initialize the PREP2.0 service 
# with a formatted CouchDB instance.

# check for root permissions
if ! id | grep -q "uid=0(root)" ; then
	echo "ERROR:  must be root in order to run this script"
	exit 1
fi

# check for leftover installations
if [ -e "/home/prep2" ]; then
	echo "WARNING: There is a version of PREP2.0 installed under /home/prep2/. Removing..."
	rm -rf /home/prep2
	
	# kill already running instance of cherrypy
	sudo kill `ps -ef | grep /home/prep2/main.py | grep root | awk '{print $2}'` &> /dev/null
	
	# kill running instance of couchdb
	sudo /etc/init.d/couchdb stop
fi

# check for options
usage()
{
cat << EOF
usage: $0 options

This script installs PREP2 service on a SLC6 environment.

OPTIONS:
	-h      		Show this message
	-u USER			Username
	-g GROUP		Groupname (Defaults to 'zh' )
	-v      		Verbose
EOF
}

user=
group=

while getopts “hu:g:v” OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         u)
             user=$OPTARG
             ;;
	 g)
	     group=$OPTARG
	     ;;	
         v)
	     set -v
             ;;
         ?)
             usage
             exit
             ;;
     esac
done

# create file tree
sudo mkdir -p /home/prep2/sources/

# check for credentials
if [ -z $user ]; then
	echo "ERROR: No username has been provided." 
	usage
	exit 2
fi

if [ -z $group ]; then
	group=zh
fi

# Check python version
major=$(python -c 'import sys; print(sys.version_info[:])' | awk -F"," '{print $1}' | cut -c 2)
minor=$(python -c 'import sys; print(sys.version_info[:])' | awk -F"," '{print $2}' | cut -c 2)

if [ $major -ge 2 ]; then
	if [ $major -eq 2 ]; then
		if [ $minor -lt 6 ]; then
			echo "ERROR: Your python version is too old. Please update to 2.6+ and run me again."
			exit 3
		fi
	fi
else
	echo "ERROR: Your python version is WAY too old. Please update to 2.6+ and run me again."
	exit 3
fi

# install setuptools (if installed do nothing)
sudo yum install python-setuptools.noarch

# install httplib2
sudo yum install python-httplib2.noarch

# install CherryPy
cd prep2/sources/
wget http://download.cherrypy.org/cherrypy/3.2.2/CherryPy-3.2.2.tar.gz
tar xvfs CherryPy-3.2.2.tar.gz
cd CherryPy-3.2.2/
sudo python setup.py install

# install Jinja2
cd /home/prep2/sources/
wget http://pypi.python.org/packages/source/J/Jinja2/Jinja2-2.6.tar.gz
tar xvfs Jinja2-2.6.tar.gz
cd Jinja2-2.6/
sudo python setup.py install

### checkout from svn PREP2.0 source
cd /home/prep2/
svn co svn+ssh://$user@svn.cern.ch/reps/CMSUserCode/trunk/prep2/nikolas/prep2 .

# checkout WMCore
mkdir WMCore
svn co svn+ssh://$user@svn.cern.ch/reps/CMSDMWM/WMCore/trunk/src/python/WMCore WMCore/

# Check if there is an iptables rule
iprule=`sudo iptables -L --numeric | grep ACCEPT | grep 'tcp dpt:80'`
if [ -z "$iprule" ]; then
	sudo iptables -I INPUT `sudo iptables --numeric --line-numbers -L INPUT | cut -b 1 | tr -d [:alpha:][:cntrl:][:blank:] | wc -m` -p tcp --dport 80 -j ACCEPT || sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
fi

# remove versioning from WMCore
cd /home/prep2/WMCore
rm -rf `find . | grep .svn`
rm /home/prep2/sources/*.tar.gz

# install CouchDB
sudo yum install couchdb.x86_64

# start CouchDB
sudo /etc/init.d/couchdb start

# wait one second (fix for the couchdb delay in responding)
sleep 1s

# format CouchDB to PREP2.0
sh /home/prep2/maintenance/reset/reset_db.sh

# chage ownership of the service
cd /home/
sudo chown -R $user:$group prep2/

# reboot
echo 'Installation complete.'

echo "You have to reboot to complete the process. Reboot now? [y/n]:"
read choice

if [ "$choice" == "y" ]; then
	sudo reboot
else
	echo "Aborting..."
fi
