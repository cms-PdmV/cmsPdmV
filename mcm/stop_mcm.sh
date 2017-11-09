kill `ps -e -f | grep main | grep python | awk '{print $2}'`
python2.6 main_tenance.py &> /dev/null
