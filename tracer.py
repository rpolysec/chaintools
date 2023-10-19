import configparser
import argparse
import sys
from datetime import datetime
from datetime import timezone
from decimal import *
import json
from etherscan import Etherscan
from web3 import Web3
from pathlib import Path
import os.path
import time

# api key for etherscan
etherscan_api_key = ''

# locations for various files
home_dir = ''
cache_dir = ''
tainted_tx_dir = ''
csv_tx_dir = ''
attrib_file = ''

getcontext().prec = 18

# A queue tracking FIFO withdrawal of tainted or non tainted funds
FundsQueue = []
# Is the next withdrawal tainted?
TaintedFront = False
# Are the funds to be withdrawn last tainted?
TaintedBack = False
# List of potentially new tainted transactions
new_taintedTx = {}
# List of addresses we have attribution for
attribs = {}

verbose = False

#---------------------------
# Application will either:
#    Update txn cache given a file with a list of addresses
#    Trace Ethereum transactions given a starting address
def main():

    config = configparser.ConfigParser()
    config.read('/etc/chaintools.config')
    
    # these have to be cleared after every trace
    global TaintedBack
    global TaintedFront
    global FundsQueue
    global new_taintedTx
    global attribs

    # read in the configuration
    etherscan_api_key = config['keys']['EtherscanAPI']
    home_dir = config['locations']['HomeDir']
    cache_dir = config['locations']['CacheDir']
    tainted_tx_dir = config['locations']['TaintedTxDir']
    csv_tx_dir = config['locations']['CsvTxDir']
    attrib_file = config['locations']['AttribFile']

    # list of ethereum addresses we have attribution for
    a_file = open(attrib_file)
    attrib_str = a_file.read()
    attribs = json.loads(attrib_str)

    args = parse_arguments()

    # loop through the addresses in the file and cache new transactions locally
    if args.address_file:
        update_txn_cache(args.address_file)
    # given an address figure out which transactions contain tainted funds
    elif args.address:
        # make sure we're always dealing with checksum version of addresses
        address = args.address
        if not Web3.is_checksum_address(address):
            address = Web3.to_checksum_address(address)

        # trace will return a list of interesting addresses and services that received
        # tainted funda and write out a csv of all ethereum transactions for the target wallet
        # in a friendly format
        add_of_interest,services = trace(address,args.update)

        print(json.dumps(services,indent=2))
        
        for a in add_of_interest:
            print(a)

#----------------------------
# Update txn cache for addresses in the provided
# file, listed one per line
def update_txn_cache(address_file):
    addrs = []

    # read addresses into an array
    f = open(address_file)
    for a in f:
        # try to always deal with checksum addresses
        address = a.strip()
        if not Web3.is_checksum_address(address):
            address = Web3.to_checksum_address(address)
        addrs.append(address)
    
    cache_tx = []
    for a in addrs:
        # get a list of txns
        cache_tx = update_local_cache(a)
        # if there is more then one txn write them out
        if len(cache_tx) > 0:
            write_cache_tx(a,cache_tx)
        # clear txns to prepare for the next batch
        cache_tx = []
        # sleep a bit so we don't hit the rate limit
        time.sleep(3)

#--------------------------
# Trace Ethereum from this address to the set of addresses that receive
# tainted funds from this one
# checksum addresses
def trace(address,update):
    # will contain address attributions load in main
    global attribs

    # make sure we're dealing with checksum versions of addresses
    if not Web3.is_checksum_address(address):
        address = Web3.to_checksum_address(address)

    # build a list of tainted addresses
    taintedAddresses = []
    # build a dictionary of tainted services
    taintedServices = {}

    print('Tracing: {}'.format(address))
    # read in cached txns, but we'll always recalculate tainted and unknown funds in case we get new information
    cache_tx = get_local_cache(address)
    # if update is true we'll update the txn cache for this address
    if update:
        # find the largest block in our cache
        last_cached_block = find_largest_block(cache_tx)
        # only grab new transactions from the largest block on
        cache_tx = get_new_transactions(address,last_cached_block,cache_tx)
        # write the cached tx's out
        write_cache_tx(address,cache_tx)

    # build a structure that holds all known tainted txns stored locally and found using earlier traces
    taintedtx = build_tainted_txn_table(address)
    
    # Tainted balance is updated with each txn containing tainted funds
    TBalance = Decimal(0.0)
    # Unknown balance is updated with each txn containing funds from an unknown (untainted) source 
    UBalance = Decimal(0.0)
    # Total Balance
    Balance = Decimal(0.0)

    # write out a new header row
    # this is intended to create a user friendly summary of a simpe ethereum transaction
    txn_out = open('{}_txn.csv'.format(address),'w')
    txn_out.write('Date(UTC),Credit,Debit,Balance,TCredit,TDebit,TBalance,UCredit,UDebit,UBalance,TXID,Src,Dest,Name,Notes\n')

    # Is the address we're tracing a service? We can't trace through them, so ignore debits
    DisableDebits = False
    if address in attribs:
        if attribs[address]['category'] in ['exchange','decentralized exchange','gambling','merchant services']:
            DisableDebits = True
            print('Target address is a service, disabling debits')

    # each line should be a json blob
    for t in cache_tx:
        # values reset for every txn tracking how much of each tx was tainted or untainted
        TCredit = Decimal(0.0)
        TDebit = Decimal(0.0)
        UCredit = Decimal(0.0)
        UDebit = Decimal(0.0)
        gas = False

        # if 'to' is empty then pull the address out of the contract address field
        a_to = t['to']
        if a_to == '':
            a_to = t['contractAddress']

        # convert to the checksum version... this should work
        try:
            a_to = Web3.to_checksum_address(a_to)
        except:
            print(t)

        # from address should always exist, get the checksum version
        a_from = Web3.to_checksum_address(t['from'])

        comment = ''
        name = ''
        category = ''

        # check if we have any attribution for the receiving address
        if a_to != address and a_to in attribs:
            comment = '{} {}'.format(attribs[a_to]['name'],attribs[a_to]['category'])
            name = attribs[a_to]['name']
            category = attribs[a_to]['category']
        
        # check if this txn is in the local tainted funds list
        if t['hash'] in taintedtx and Decimal(t['value']) > 0 and Web3.to_checksum_address(taintedtx[t['hash']]['dst']) == address:
                # use the values we already have to from tainted transactions we know about
                TCredit, UCredit = processTaintedCredit(taintedtx[t['hash']]['queue'],Web3.from_wei(Decimal(t['value']), 'ether'))
                TBalance = TBalance + TCredit
                UBalance = UBalance + UCredit
                Balance = Balance + TCredit + UCredit
                comment = taintedtx[t['hash']]['comment']
        # when there is a debit we reproduce the order of the funds so we are still following
        # the correct tainted coins
        # WE DO NOT TRACE THROUGH SERVICES
        elif a_from == address: # confirm we have a debit
            if not DisableDebits:
                TDebit, UDebit, q = processDebit(Web3.from_wei(Decimal(t['value']), 'ether'))
                TBalance = TBalance - TDebit
                UBalance = UBalance - UDebit
                Balance = Balance - TDebit - UDebit
                gas = True
                # check if we have attribution
                if TDebit > 0:
                    if not a_to in taintedServices and category in ['exchange','decentralized exchange','token smart contract','gambling','merchant services','unnamed service']:
                        taintedServices[a_to] = {'name':name, 'category':category}
                    elif not a_to in taintedAddresses:
                        taintedAddresses.append(a_to)
                    # create a new tainted transaction with the following format
                    new_taintedTx[t['hash']] = {'src':a_from, 'dst':a_to, 'queue':q, 'token': 'eth', 'comment': comment}
        # we can have a 0.0 value txn, treat it as a credit from unknown source
        elif a_to == address:
            UCredit = processCredit(Web3.from_wei(Decimal(t['value']), 'ether'))
            UBalance = UBalance + UCredit
            Balance = Balance + UCredit
        #Date(0), Credit(1), Debit(2), Balance(3), TCredit(4), TDebit(5), TBalance(6), UCredit(7), UDebit(8),
        # UBalance(9), TXID(10), Src(11), Dest(12), ENS(13), Notes(14)
        dt_object = datetime.utcfromtimestamp(int(t['timeStamp']))
        timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S')
        txn_out.write('{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n'.format(
            timestamp,TCredit+UCredit,TDebit+UDebit,Balance,TCredit,TDebit,TBalance,UCredit,UDebit,UBalance,t['hash'],a_from,a_to,name,category
        ))

        # make sure we account for gas when figuring out the balance
        if gas and 'gasPrice' in t:
            gas_val = Web3.from_wei((Decimal(t['gasPrice'])*Decimal(t['gasUsed'])),'ether')
            TDebit, UDebit, q = processDebit(gas_val)
            credit = Decimal(0)
            TBalance = TBalance - TDebit
            UBalance = UBalance - UDebit
            Balance = Balance - TDebit - UDebit
            txn_out.write('{},{},{},{},0,{},{},0,{},{},{},{},(fees),{},{}\n'.format(
                timestamp,credit,gas_val,Balance,TDebit,TBalance,UDebit,UBalance,t['hash'],a_from,name,category
            ))

    writeOutTaintedTxns('eth')
    print('{} balance {}'.format(address,Balance))
    return taintedAddresses, taintedServices

#----------------------------
# With every debit we have to ensure we follow any tainted funds
# by creating a tainted transaction if tainted funds leave the address
def processDebit(val):
    global TaintedBack
    global TaintedFront
    global FundsQueue

    verbose = False
    # grab the full value of the debit
    d_remain = val
    t_debit = Decimal(0.0)
    u_debit = Decimal(0.0)
    # work through the queue until we run out of debit
    debit_q = []
    while d_remain > 0 and len(FundsQueue)>0:
        if verbose: print('========================')
        # we're removing more funds then what is at the front of the queue, this will pop
        if verbose: print('{},{}'.format(d_remain,FundsQueue))
        if d_remain >= FundsQueue[0]:
            if verbose: print('d_remain >= FundsQueue[0]')
            d_remain = d_remain - Decimal(FundsQueue[0])
            if TaintedFront:
                t_debit = t_debit + Decimal(FundsQueue[0])
                debit_q.append({'tainted':True,'value':'{0:f}'.format(Decimal(FundsQueue[0]))})
                TaintedFront = False
                FundsQueue.pop(0)
                if len(FundsQueue) == 0:
                    #reset
                    TaintedFront = False
                    TaintedBack = False
            else:
                u_debit = u_debit + Decimal(FundsQueue[0])
                debit_q.append({'tainted':False,'value':'{0:f}'.format(Decimal(FundsQueue[0]))})
                TaintedFront = True
                FundsQueue.pop(0)
                if len(FundsQueue) == 0:
                    #reset
                    TaintedFront = False
                    TaintedBack = False
        # this is the easy case, just subtract the value from what is in the front
        else:
            if verbose: print('d_remain < FundsQueue[0]')
            FundsQueue[0] = FundsQueue[0] - d_remain
            if TaintedFront:
                t_debit = t_debit + d_remain
                debit_q.append({'tainted':True,'value':'{0:f}'.format(d_remain)})
            else:
                u_debit = u_debit + d_remain
                debit_q.append({'tainted':False,'value':'{0:f}'.format(d_remain)})
            d_remain = Decimal(0.0)
        if verbose: print('t_debit: {} u_debit: {}'.format(t_debit,u_debit))
    return t_debit, u_debit, debit_q
#----------------------------
# Process a credit from an unknown or legitimate source which
# includes transactions with 0 value for completness sake
def processCredit(val):
    global TaintedBack
    global TaintedFront
    global FundsQueue

    # the most recent funds in the queue are tainted, add untainted funds
    if TaintedBack:
        FundsQueue.append(val)
        TaintedBack = False
        if len(FundsQueue) == 1:
            TaintedFront = False
    # the most recent funds in the queue are not tainted, just add them together
    else:
        # the queue is empty, add this value
        if len(FundsQueue) == 0:
            FundsQueue.append(val)
        else:
            # the funds at the back of the queue aren't tainted, just add them to existing balance
            FundsQueue[len(FundsQueue)-1] = FundsQueue[len(FundsQueue)-1] + val
    return val

#----------------------------
# Process a known tainted credit. The credit can containt a mix
# of tainted and non-tainted funds, and the tainted credit object
# contains a queue processed in order to make sure the right balances
# are adjusted and the main funds queue is changed appropriately
def processTaintedCredit(txn_q,exp_val):
    global TaintedBack
    global TaintedFront
    global FundsQueue

    tot_val = Decimal(0.0)
    t_credit = Decimal(0.0)
    u_credit = Decimal(0.0)

    for item in txn_q:
        if item['tainted']:
            t_credit = t_credit + Decimal(item['value'])
            if TaintedBack:
                FundsQueue[len(FundsQueue)-1] = FundsQueue[len(FundsQueue)-1] + Decimal(item['value'])
            else:
                FundsQueue.append(Decimal(item['value']))
                TaintedBack = True
                if len(FundsQueue) == 1:
                    TaintedFront = True
        elif not item['tainted']:
            u_credit = u_credit + Decimal(item['value'])
            if not TaintedBack:
                # hit index out of range here... check if len is 1
                if (len(FundsQueue)==0):
                    FundsQueue.append(Decimal(item['value']))
                else:
                    FundsQueue[len(FundsQueue)-1] = FundsQueue[len(FundsQueue)-1] + Decimal(item['value'])
            else:
                FundsQueue.append(Decimal(item['value']))
                TaintedBack = False
                if len(FundsQueue) == 1:
                    TaintedFront = False
        tot_val = t_credit + u_credit
    #print('Expected:{}, TotalVal: {}'.format(exp_val,tot_val))
    return (t_credit,u_credit)

#---------------------------------
# Write out all the tainted transactions
# Reviewd for checksum addresses
def writeOutTaintedTxns(token):
    global new_taintedTx
    rel_taintedTxFiles = {}

    # load all relevant tainted transaction files
    # this for loop ONLY loads and doesn't change things yet
    for t_txn in new_taintedTx:
        dst = new_taintedTx[t_txn]['dst']
        if not Web3.is_checksum_address(dst):
            dst = Web3.to_checksum_address(dst)

        # check if there is already a file for this receiving address
        filename = '{}/td_{}.json'.format(tainted_tx_dir,dst)
        if os.path.isfile(filename):
            # if yes, open the file, read in the json and then check if this transaction is there yet
            tx_file = open(filename)
            tx_str = tx_file.read()
            txs = json.loads(tx_str)
            # this is where we would check if there is another transaction
            rel_taintedTxFiles[dst] = txs

    # while we're working with the queue's we want them in Decimal format, change them before writing them out
    for t_txn in new_taintedTx:
        d_addr = new_taintedTx[t_txn]['dst']
        if not d_addr == '(fees)' and not Web3.is_checksum_address(d_addr):
            d_addr = Web3.to_checksum_address(d_addr)

        s_addr = new_taintedTx[t_txn]['src']
        if not Web3.is_checksum_address(s_addr):
            s_addr = Web3.to_checksum_address(s_addr)

        if not d_addr == '(fees)' and d_addr in rel_taintedTxFiles:
            # check if this transaction is in there
            if not t_txn in rel_taintedTxFiles[d_addr]:
                # add this transaction in
                rel_taintedTxFiles[d_addr][t_txn] = {'src':s_addr, 'dst':d_addr, 'queue':new_taintedTx[t_txn]['queue'], 'token': token, 'comment': ''}
            else:
                # make sure they match, if they don't we should do something
                if rel_taintedTxFiles[d_addr][t_txn]['src'] != s_addr or rel_taintedTxFiles[d_addr][t_txn]['dst'] != d_addr:
                    print('Tainted transaction addresses do not match')
                    print(rel_taintedTxFiles[d_addr][t_txn])
                    print({'src':s_addr, 'dst':d_addr, 'queue':new_taintedTx[t_txn]['queue'], 'token': token, 'comment': ''})
        elif not d_addr == '(fees)':
            rel_taintedTxFiles[d_addr] = {}
            rel_taintedTxFiles[d_addr][t_txn] = {'src':s_addr, 'dst':d_addr, 'queue':new_taintedTx[t_txn]['queue'], 'token': token, 'comment': ''}

    # print out all the trainted transaction files
    for txn_file in rel_taintedTxFiles:
        tainted_out = open('td_{}.json'.format(txn_file),'w')
        tainted_out.write(json.dumps(rel_taintedTxFiles[txn_file],indent=2))

#----------------------------
# If there is a tainted transaction file in
# this directory, read tainted transactins from it
def build_tainted_txn_table(address):
    if not Web3.is_checksum_address(address):
        address = Web3.to_checksum_address(address)
    taintedTx = {}
    tainted = '{}/td_{}.json'.format(tainted_tx_dir,address)
    print("Looking for {}".format(tainted))
    # if this file exists then we're dealing with eth, if not determine the token
    if Path(tainted).is_file():
        taintedTx_file = open(tainted)
        taintedTx_str = taintedTx_file.read()
        taintedTx = json.loads(taintedTx_str)
    return taintedTx

#----------------------------
# write out all our cached transactions
# cheksum address
def write_cache_tx(a,cache_tx):
    if not Web3.is_checksum_address(a):
        a = Web3.to_checksum_address(a)
    filename = '{}/{}_cache.json'.format(cache_dir,a)
    tx_file = open(filename,'w')
    for t in cache_tx:
        # this is one json object per line
        tx_file.write(json.dumps(t))
        tx_file.write('\n')

#---------------------------
# Check if we already have a local cache
# Load transactions into memory
# Check the block number of the most recent transaction
# Get all transactions for this address since the last one
# checksum address
def update_local_cache(a):
    if not Web3.is_checksum_address(a):
        a = Web3.to_checksum_address(a)
    cache_tx = get_local_cache(a)
    if len(cache_tx) > 20000:
        print('skipping update, already has > 20000 transactions')
    else:
        last_cached_block = find_largest_block(cache_tx)
        cache_tx = get_new_transactions(a,last_cached_block,cache_tx)
    return cache_tx

#----------------------------
# Starting from the last block we've cached, get all new
# transactions
# checksum address
def get_new_transactions(a, last_cached_block, cache_tx):
    eth = Etherscan(etherscan_api_key)
    if not Web3.is_checksum_address(a):
        a = Web3.to_checksum_address(a)
    
    # get normal transactions
    results_external = []
    try:
        results_external = eth.get_normal_txs_by_address(a, last_cached_block+1, 99999999, 'asc')
    except AssertionError as msg:
        print(msg)
    
    # get internal transactions
    results_internal = []
    try:
        results_internal = eth.get_internal_txs_by_address(a, last_cached_block+1, 99999999, 'asc')
    except AssertionError as msg:
        print(msg)

    i = 0
    j = 0

    while i < len(results_internal) and j < len(results_external):
        if results_internal[i]['blockNumber'] < results_external[j]['blockNumber']:
            cache_tx.append(results_internal[i])
            i+=1
        else:
            cache_tx.append(results_external[j])
            j+=1

    while i < len(results_internal):
        cache_tx.append(results_internal[i])
        i+=1

    while j < len(results_external):
        cache_tx.append(results_external[j])
        j+=1

    total = len(results_internal) + len(results_external)
    print('Retrieved {} txns'.format(total))
    return cache_tx

#---------------------------
# For now I'm assuming the json read in
# will not be sorted by block number. This is
# simple brute force way to find the largest block we
# have in our cache
# checksum address
def find_largest_block(cache_tx):
    largest_block = 0
    if len(cache_tx) > 0:
        print("expected largest block: {}".format(cache_tx[len(cache_tx)-1]['blockNumber']))
    for t in cache_tx:
        if int(t['blockNumber']) > largest_block:
            largest_block = int(t['blockNumber'])
    print("largest block found: {}".format(largest_block))
    return largest_block

#---------------------------
# if there is a local cache already, read it in
# otherwise return an empty dictionsary
# checksum address
def get_local_cache(a):
    if not Web3.is_checksum_address(a):
        a = Web3.to_checksum_address(a)
    print('Getting local cache: {}'.format(a))
    txs = []
    # the cache is stored in 0x<address>_cache.json
    filename = '{}/{}_cache.json'.format(cache_dir,a)
    if not Path(filename).is_file():
        print('no existing cache')
    else:
        print('Found file: {}'.format(filename))
        tx_file = open(filename)
        for line in tx_file.readlines():
            jobject = json.loads(line.strip())
            txs.append(jobject)
    return txs

#---------------------------
# parse arguments and return a list of addresses
# checksum address
def parse_arguments():
    parser = argparse.ArgumentParser(
                    prog='ChainTools',
                    description='Scripts for manipulating transaction data',
                    epilog='happy hunting')
    parser.add_argument('-f', dest='address_file', action='store', required=False, help='list of addresses to cache txns')
    parser.add_argument('-t', dest='address', action='store', required=False, help='address to start tracing from')
    parser.add_argument('-u', dest='update', action='store_true', required=False, default=False, help='pull new transactions?')
    args = parser.parse_args()

    return args

if __name__ == "__main__":
    main()
