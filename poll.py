#!/usr/bin/env python
"""
This is a multiprocessing wrapper for Net-SNMP with output to Graphite
Based on code from these sources
http://www.copyandwaste.com/posts/view/multiprocessing-snmp-with-python/
http://www.ibm.com/developerworks/aix/library/au-multiprocessing/
"""

from pprint import pprint
import csv
import sys
import time
import os
import platform
import subprocess
from socket import socket
import netsnmp
from multiprocessing import Process, Queue, current_process

COMMUNITY = "public"
LISTFILE = "hosts.csv"
GRAPHITEPATH = "app.poll"

# interface mib
os.environ['MIBS'] = 'IF-MIB'

lines = []

CARBON_SERVER = 'localhost'
CARBON_PORT = 2003

class HostRecord():
    """This creates a host record"""
    def __init__(self,
                 hostname = None,
				 oid = None,
                 iid = None,
                 query = None):
        self.hostname = hostname
        self.oid = oid
        self.iid = iid
        self.query = query

class SnmpSession():
    """A SNMP Session"""
    def __init__(self,
                oid = "sysDescr",
                iid="0",
                Version = 2,
                DestHost = "localhost",
                Community = "public",
                Verbose = True,
                ):
        self.oid = oid
        self.Version = Version
        self.DestHost = DestHost
        self.Community = Community
        self.Verbose = Verbose
        self.var = netsnmp.Varbind(oid, iid)
        self.hostrec = HostRecord()
        self.hostrec.hostname = self.DestHost
        self.hostrec.oid = oid
        self.hostrec.iid = iid

    def query(self):
        """Creates SNMP query

        Fills out a Host Object and returns result
        """
        try:
            result = netsnmp.snmpget(self.var,
                                Version = self.Version,
                                DestHost = self.DestHost,
                                Community = self.Community)
            self.hostrec.query = result
        except Exception, err:
            if self.Verbose:
                print err
            self.hostrec.query = None
        finally:
            return self.hostrec

def make_query(host):
    """This does the actual snmp query

    This is a bit fancy as it accepts both instances
    of SnmpSession and host/ip addresses.  This
    allows a user to customize mass queries with
    subsets of different hostnames and community strings
    """
    if isinstance(host,SnmpSession):
        return host.query()
    else:
        s = SnmpSession(DestHost=host)
        return s.query()

# Function run by worker processes
def worker(input, output):
    for func in iter(input.get, 'STOP'):
        result = make_query(func)
        output.put(result)

def tographite():
    now = int(time.time())
    sock = socket()
    try:
            sock.connect( (CARBON_SERVER,CARBON_PORT) )
    except:
            print "Couldn't connect to %(server)s on port %(port)d, is carbon-agent.py running?" % { 'server':CARBON_SERVER, 'port':CARBON_PORT }
            sys.exit(1)

    for i in range(len(lines)):
      message = '\n'.join(lines) + '\n' #all lines must end in a newline
      sock.sendall(message)

def main():
    """Runs everything"""

    ifile  = open(LISTFILE, "rb")
    reader = csv.reader(ifile)
    rownum = 0
    hosts = []
    for row in reader:
        # Save header row.
        if rownum == 0:
            header = row
        else:
            hosts += [SnmpSession(DestHost=row[0], Community=COMMUNITY, oid=row[1], iid=row[2])]

        rownum += 1

    #print hosts
    ifile.close()

    #clients

    NUMBER_OF_PROCESSES = len(hosts)

    # Create queues
    task_queue = Queue()
    done_queue = Queue()

    #submit tasks
    for host in hosts:
        task_queue.put(host)

    #Start worker processes
    for i in range(NUMBER_OF_PROCESSES):
        Process(target=worker, args=(task_queue, done_queue)).start()

     # Get and print results
    #print 'Unordered results:'
	
    for i in range(len(hosts)):
        VALUE=done_queue.get()

	# a bit hardcoded here, suspect we will want to do it on per-customer
	# basis if we do more in future, so i've added a graphite tier for 
        # the customer name

        print '\t', VALUE.query[0], VALUE.hostname, VALUE.oid, VALUE.iid
        lines.append("%s.%s.%s.%s %s %s" % (GRAPHITEPATH, VALUE.hostname, VALUE.oid, VALUE.iid, VALUE.query[0], int(time.time())) )



    # Tell child processes to stop
    for i in range(NUMBER_OF_PROCESSES):
        task_queue.put('STOP')
        #print "Stopping Process #%s" % i

if __name__ == "__main__":
    main()
    tographite()
