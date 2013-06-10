ps aux | grep python2.6 | grep -v grep | awk -F\   '{print $2;}' | head -n 1 | xargs -IIII sh -c "kill -9 'III'"; nohup python2.6 main.py &>acmw15.log &
