#!/bin/bash
# run once, but just use the timeout command

# Note, the timeout command stops the python script from getting stuck
# in a locked state due to any snmp issues - slow collection etc
# It's better to just start again and hope the problem was resolved
# as we don't want to end up with a whole lot of stuck processes

cd /opt/poller
timeout 15 ./poll.py

