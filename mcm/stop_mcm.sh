kill `ps -e -f | grep main | grep python | awk '{print $2}'`
sleep 3
kill -9 `ps -e -f | grep main | grep python | awk '{print $2}'`
python2.6 main_tenance.py