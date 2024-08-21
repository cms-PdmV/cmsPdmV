#!/usr/bin/env python2.6
import time
import os
import subprocess

TIME_FORMAT = "%Y_%m_%d_%H_%M"
BACKUP_DIR = "/afs/cern.ch/work/p/pdmvserv/public/couchBACK_UP"
current_time = time.strftime(TIME_FORMAT)
os.system("tar -zcvf "+ current_time+".tar.gz /var/lib/couchdb/*.couch")
print("Tarred couchDB. Preparing to move it to BACKUP-DIR")
current_size = os.path.getsize(os.path.join(os.getcwd(),current_time+".tar.gz")); ##get current backup file size
#print current_size

##get amount of space in BACKUP_DIR
#p = subprocess.Popen("fs lq -p "+BACKUP_DIR, stdout=subprocess.PIPE,shell=True)
#output = p.communicate()[0]
#info = output.split("\n")[1] ##slpit by EOL and get second line of fs command -> the one with size numbers
#data = info.split(" ")
#data = list(set(data))
#data.remove("")
#number_of_files =  len(os.listdir(BACKUP_DIR))
#print data
#free_space = int(data[2])-int(data[1])
#print "Free space in %s : %i KB" %(BACKUP_DIR,free_space)
#if number_of_files < free_space*1024/current_size:
#os.system("mv *.tar.gz "+BACKUP_DIR)
#else:
#    "NOT ENOUGH FREE SPACE in:%s" %(BACKUP_DIR)
t = os.system("mv *.tar.gz "+BACKUP_DIR)
if t == 0:
    print("Done")
else:
    print("ERROR")

