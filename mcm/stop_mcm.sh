kill -9 `ps -e -f | grep main | grep python | awk '{print $2}'`
kill -9 `ps -e -f  | grep mcm | grep -v $$ | awk '{print $2}'` 
python2.6 main_tenance.py
