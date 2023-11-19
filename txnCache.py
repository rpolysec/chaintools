from web3 import Web3
import time
import json
from etherscan import Etherscan
from pathlib import Path

class TxnCache():

    def __init__(self,cache_dir,key):
        self.cache_dir = cache_dir
        self.eth = Etherscan(key)

    #----------------------------
    # Update txn cache for addresses in the provided
    # file, listed one per line
    def update_txn_cache_from_file(self,address_file):
        addrs = []

        # read addresses into an array
        f = open(address_file)
        for a in f:
            # try to always deal with checksum addresses
            address = a.strip()
            if not Web3.is_checksum_address(address):
                address = Web3.to_checksum_address(address)
            addrs.append(address)
        
        self.update_txn_cache(addrs)
    

    #----------------------------
    # Update txn cache for addresses in the provided
    # file, listed one per line
    def update_txn_cache(self,addrs):
        for a in addrs:
            # get a list of txns
            cache_tx = self.update_local_cache(a,'ext')
            if len(cache_tx) > 0:
                self.write_cache_tx(a,cache_tx,'ext')

            # get a list of internal txns
            cache_tx = self.update_local_cache(a,'int')
            if len(cache_tx) > 0:
                self.write_cache_tx(a,cache_tx,'int')

            # get a list of erc20 transfers
            cache_tx = self.update_local_cache(a,'erc20')
            if len(cache_tx) > 0:
                self.write_cache_tx(a,cache_tx,'erc20')

            # sleep a bit so we don't hit the rate limit
            time.sleep(3)

    #----------------------------
    # write out all our cached transactions
    # cheksum address
    def write_cache_tx(self,a,cache_tx,suffix):
        if not Web3.is_checksum_address(a):
            a = Web3.to_checksum_address(a)
        filename = '{}/{}_{}_cache.json'.format(self.cache_dir,a,suffix)
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
    def update_local_cache(self,a,suffix):
        if not Web3.is_checksum_address(a):
            a = Web3.to_checksum_address(a)
        cache_tx = self.get_local_cache(a,suffix)
        if len(cache_tx) > 20000:
            print('skipping update, already has > 20000 transactions')
        else:
            last_cached_block = self.find_largest_block(cache_tx)
            cache_tx = self.get_new_transactions(a,last_cached_block,cache_tx,suffix)
        return cache_tx

    #----------------------------
    # Starting from the last block we've cached, get all new
    # transactions
    def get_new_transactions(self,a, last_cached_block, cache_tx, suffix):
        start = len(cache_tx)
    
        if not Web3.is_checksum_address(a):
            a = Web3.to_checksum_address(a)
    
        # get normal transactions
        results = []
        try:
            if suffix == 'ext':
                results = self.eth.get_normal_txs_by_address(a, last_cached_block+1, 99999999, 'asc')
            elif suffix == 'int':
                results = self.eth.get_internal_txs_by_address(a, last_cached_block+1, 99999999, 'asc')
            elif suffix == 'erc20':
                results = self.eth.get_erc20_token_transfer_events_by_address(a, last_cached_block+1, 99999999, 'asc')
        except AssertionError as msg:
            #print(msg)
            exception = True
    
        i = 0

        while i < len(results):
            cache_tx.append(results[i])
            i+=1

        total = len(cache_tx) - start
        return cache_tx

    #---------------------------
    # For now I'm assuming the json read
    # will not be sorted by block number. This is a
    # simple brute force way to find the largest block we
    # have in our cache
    # TODO Use a SortedList here
    def find_largest_block(self,cache_tx):
        largest_block = 0
        for t in cache_tx:
            if int(t['blockNumber']) > largest_block:
                largest_block = int(t['blockNumber'])
        return largest_block

    #---------------------------
    # if there is a local cache already, read it in
    # otherwise return an empty dictionary
    def get_local_cache(self,a,suffix):
        if not Web3.is_checksum_address(a):
            a = Web3.to_checksum_address(a)
        txs = []
        # the cache is stored in 0x<address>_cache.json
        filename = '{}/{}_{}_cache.json'.format(self.cache_dir,a,suffix)
        if Path(filename).is_file():
            tx_file = open(filename)
            for line in tx_file.readlines():
                jobject = json.loads(line.strip())
                txs.append(jobject)
        return txs
