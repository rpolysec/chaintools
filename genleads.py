import configparser
import os
import argparse
from web3 import Web3
import json
from decimal import *
from etherscan import Etherscan

config = configparser.ConfigParser()
config.read('/etc/chaintools.config')

etherscan_api_key = config['keys']['EtherscanAPI']
tainted_tx_dir = config['locations']['TaintedTxDir']
attrib_file = config['locations']['AttribFile']
mtaint = {}

# load attributions for addresses we know about
attrib_file = open(attrib_file)
attrib_str = attrib_file.read()
attribs = json.loads(attrib_str)

parser = argparse.ArgumentParser(
                    prog='ChainTools',
                    description='Scripts for manipulating transaction data',
                    epilog='happy hunting')
parser.add_argument('-a', dest='address', action='store', help='address for leads')
parser.add_argument('-v', dest='verbose', action='store_true', help='print all output')
args = parser.parse_args()

address = args.address
if not Web3.is_checksum_address(address):
    address = Web3.to_checksum_address(address)

eth = Etherscan(etherscan_api_key)
result = eth.get_eth_balance(address)
bal = Web3.from_wei(Decimal(result), 'ether')

# load all tainted transactions we know about
for file in os.listdir(tainted_tx_dir):
    if 'td_' in file:
        tainted_tx_file = open(tainted_tx_dir + '/' + file)
        tainted_tx_str = tainted_tx_file.read()
        tainted = json.loads(tainted_tx_str)

        for t in tainted:
            if not t in mtaint:
                mtaint[t] = tainted[t]


# print out results but also look for addresses of high interest
aoi = {}
total_sent = Decimal(0.0)
total_rec = Decimal(0.0)
for t in mtaint:
    if mtaint[t]['dst'] == args.address:
        for entry in mtaint[t]['queue']:
            if entry['tainted']:
                total_rec = total_rec + Decimal(entry['value'])
        if mtaint[t]['src'] in attribs:
            if args.verbose:
                print('{},{},{},{}'.format(attribs[mtaint[t]['src']]['name'],attribs[mtaint[t]['src']]['category'],mtaint[t]['src'],mtaint[t]['queue']))
        else:
            if args.verbose:
                print('{},{}'.format(mtaint[t]['src'],mtaint[t]['queue']))


    if mtaint[t]['src'] == args.address:
        total = Decimal(0.0)
        if mtaint[t]['dst'] in aoi:
            total = total + aoi[mtaint[t]['dst']]
        for taint_val in mtaint[t]['queue']:
            if taint_val['tainted']:
                total = total + Decimal(taint_val['value'])
                total_sent = total_sent + Decimal(taint_val['value'])
        
        if total > 0:
            aoi[mtaint[t]['dst']] = total
            print('========{}========'.format(total))

        # calculate total tainted in queue
        if mtaint[t]['dst'] in attribs:
            if args.verbose:
                print('Service: {},{},{},{}'.format(attribs[mtaint[t]['dst']]['name'],attribs[mtaint[t]['dst']]['category'],mtaint[t]['dst'],mtaint[t]['queue']))
        else:
            if args.verbose:
                print('{},{}'.format(mtaint[t]['dst'],mtaint[t]['queue']))
sorted = []

for o in aoi:
    if len(sorted) > 0:
        found = False
        i=0
        while i < len(sorted)-1 and not found:
            if sorted[i][1] < aoi[o]:
                sorted.insert(i,[o,aoi[o]])
                i = len(sorted)
                found = True
            i+=1
        if not found:
            sorted.append([o,aoi[o]])
    else:
        sorted.append([o,aoi[o]])

for i in sorted:
    print(i)

print('Total Recieved: {}'.format(total_rec))
print('Total Sent: {}'.format(total_sent))
print('Eth Balance: {}'.format(bal))
