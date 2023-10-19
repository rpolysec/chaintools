from datetime import datetime
from datetime import timedelta
from decimal import *
import json
from web3 import Web3
from pathlib import Path
import argparse
import sys
import networkx as nx
from pyvis.network import Network
import configparser

getcontext().prec = 18

# List of addresses we have attribution for
attribs = {}

# dictionary of addresses-->dictionary of dates-->balances
# address, date, date, date, date...
# <address>, bal, bal, bal, bal...
balances = {}

# amount of fees spent on each day, date is the key and result is a running balance
fees = {}

# one graph for every day of funds movements
graphs = {}

#---------------------------
# Application will either:
# List tainted values in wallets for every day in a given range
def main():

    config = configparser.ConfigParser()
    config.read('/etc/chaintools.config')

    attrib_file = config['locations']['AttribFile']

    outfile = open('out.csv','w')
    
    # these have to be cleared after every trace
    global attribs
    master_graph = nx.MultiDiGraph()

    # list of ethereum addresses we have attribution for
    a_file = open(attrib_file)
    attrib_str = a_file.read()
    attribs = json.loads(attrib_str)

    # parse arguments
    args = parse_arguments()

    f_matches = []
    # should always pass in a list of addresses you care about
    if args.address_file:
        address_file = open(args.address_file)
        for f in address_file:
            f_matches.append('{}_txn.csv'.format(f.strip()))
    # but you can also just build the graph based on whatever csv files you in your current directory
    else:
        # find all the files that match 0x*.csv
        p = Path('.')
        f_matches = list(p.glob('0x*.csv'))

    # each file includes tx's for an address
    for file in f_matches:
        # extract the address from the file name
        address = str(file)[0:-8]
        # for each new address create a dictionary of dates
        # not every date will have a new balance though (it might be sparse)
        balances[address] = {}

        # make sure we're always dealing with checksum version of addresses
        if not Web3.is_checksum_address(address):
            address = Web3.to_checksum_address(address)

        # every line in the file could have a new balance, and you might
        # have multiple tx's on a day, however, they are in order so the
        # last one for a given day is the one we want
        f = open(file)
        for line in f:
            if 'TDebit' in line:
                continue
            fields = line.split(',')
            # grab just day, month and year, ignore time
            newdate = fields[0][0:10]
            # grab the balance
            newbalance = fields[6]
            # this will either create a new balance/date combo or update the existing one
            balances[address][newdate] = newbalance

            # check if this line includes fees and a tainted debit
            try:
                debitval = Decimal(fields[5])
            except:
                # this should never happen so bail
                print(fields[5])
                sys.exit(0)
            if 'fees' in line and debitval > 0:
                if newdate in fees:
                    fees[newdate] = fees[newdate] + debitval
                else:
                    fees[newdate] = debitval

            # if this is a debit add an edge in the graph for this day
            if not 'fees' in line and debitval > 0:
                if newdate in graphs:
                    graphs[newdate].add_edge(fields[11][0:8],fields[12][0:8],label=fields[5][0:5])
                    master_graph.add_edge(fields[11][0:8],fields[12][0:8],label=fields[5][0:5])
                else:
                    graphs[newdate] = nx.MultiDiGraph()
                    graphs[newdate].add_edge(fields[11][0:8],fields[12][0:8],label=fields[5][0:5])
                    master_graph.add_edge(fields[11][0:8],fields[12][0:8],label=fields[5][0:5])

    # This is a where we set the starting date (hardcoded)
    dt_object = datetime.strptime(args.startdate,'%Y-%m-%d')

    dates = []
    # the ranges sets how many days we're processing
    for i in range(0,int(args.days)):
        dt_object = dt_object + timedelta(days = 1)
        timestamp = dt_object.strftime('%Y-%m-%d')
        dates.append(timestamp)

    # for each address get the tainted balance for each day
    for addr in balances:
        bal = '  0.0000'
        # filling in the dates that are missing
        # if there are no tx's for a day use the last known
        # tainted balance
        for d in dates:
            # grab the last known balance
            if d in balances[addr]:
                bal = balances[addr][d]
            # add the balance to a missing day
            else:
                balances[addr][d] = bal

    totfeesperday = []
    totalfees = Decimal(0.0)
    for d in dates:
        if d in fees:
            totalfees = totalfees + fees[d]
        totfeesperday.append(totalfees)
        
    dstr = ''
    first = True
    for d in dates:
        # lazy way to make sure we don't print out the first comma
        # when building the first line of dates (do we use this?)
        if first:
            dstr = d
            first = False
        # add the next value
        else:
            dstr = '{} {}'.format(dstr,d)
    #print(dstr)

    # added spaces to front to account for date column
    addr_str = '                        fees'
    # build a string of addresses shortened to 8 characters as the header row
    for addr in balances:
        if addr_str == '':
            addr_str = addr[0:8]
        else:
            addr_str = '{} {}'.format(addr_str,addr[0:8])
    # print the header row
    outfile.write(addr_str)
    outfile.write('\n')

    # build out each subsequent row, one for each date
    count = 0
    for d in dates:
        balstr = ''
        first = True
        total = Decimal(0.0)
        for addr in balances:
            bal = balances[addr][d]
            # track total ETH traced
            total = total + Decimal(bal)

            # do a bunch of formatting to get consistent
            # column widths
            if not '.' in bal:
                bal = bal + '.'

            if 'E' in bal:
                bal = '  0.0000'
            elif bal == '0.':
                bal = '  0.0000'
            elif Decimal(bal) == Decimal(0.0):
                bal = '  0.0000'
            elif Decimal(bal) < 10:
                bal = '  {}'.format(bal)
            elif Decimal(bal) < 100:
                bal = ' {}'.format(bal)

            if len(bal) == 4:
                bal = '{}0000'.format(bal)
            elif len(bal) == 5:
                bal = '{}000'.format(bal)
            elif len(bal) == 6:
                bal = '{}00'.format(bal)
            elif len(bal) == 7:
                bal = '{}0'.format(bal)

            # add the next balance to the balance strig, but
            # only take 8 characters
            if first:
                balstr = bal[0:8]
                first = False
            else:
                balstr = '{} {}'.format(balstr,bal[0:8])

        # print out the next row
        total = total + totfeesperday[count]
        outfile.write('{} {} {} {}'.format(d,str(total)[0:8],str(totfeesperday[count])[0:8],balstr))
        outfile.write('\n')
        count = count + 1

    nt = Network('1000px', '1000px', directed=True)
    nt.from_nx(master_graph)

    nt.show_buttons()
    nt.set_edge_smooth('dynamic')
    nt.show('graphs/master_graph.html'.format(d), notebook=False)

    for d in graphs:
        nt = Network('1000px', '1000px', directed=True)
        nt.from_nx(graphs[d])

        nt.show_buttons()
        nt.set_edge_smooth('dynamic')
        nt.show('graphs/nx_{}.html'.format(d), notebook=False)

#---------------------------
# parse arguments and return a list of addresses
# checksum address
def parse_arguments():
    parser = argparse.ArgumentParser(
                    prog='ChainTools',
                    description='Scripts for manipulating transaction data',
                    epilog='happy hunting')
    parser.add_argument('-f', dest='address_file', action='store', required=False, help='list of addresses to read transactions from')
    parser.add_argument('-s', dest='startdate', action='store', required=False, default='2023-01-01', help='date to start tracing in format YYYY-MM-DD')
    parser.add_argument('-d', dest='days', action='store', required=False, default='10', help='How many days to create graphs for')
    args = parser.parse_args()

    return args

if __name__ == "__main__":
    main()
