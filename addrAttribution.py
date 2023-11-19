from decimal import *
import json
from etherscan import Etherscan
from web3 import Web3
from ens import ENS

# Attribution data for various addresses associated
# with an investigatio
class AddrAttribution():

    def __init__(self,file,tfile,key):
        self.eth = Etherscan(key)
        alchemy_url = "https://eth-mainnet.g.alchemy.com/v2/MKix83LrE4x5qRjpO_FY6jHNVbJ9nSdS"
        self.w3 = Web3(Web3.HTTPProvider(alchemy_url))
        self.ns = ENS.from_web3(self.w3)

        attrib_file = open(file)
        attrib_str = attrib_file.read()
        self.attribs = json.loads(attrib_str)

        token_file = open(tfile)
        token_str = token_file.read()
        self.tokens = json.loads(token_str)

        self.priv_addr_cache = set()

    def validateToken(self,name,addr):
        # ignore tokens not supported
        if not name in self.tokens:
            return False
        
        # double check that the contract for this token matches what we have
        if Web3.to_checksum_address(self.tokens[name]['address']) == Web3.to_checksum_address(addr):
            return True
        else:
            # the contract address isn't what we expect, probably a fake token
            return False

    def getName(self,addr):
        if addr in self.attribs:
            return self.attribs[addr]['name']
        return 'none'

    def getCategory(self,addr):
        if addr in self.attribs:
            return self.attribs[addr]['category']
        return 'none'
    
    def isContract(self,address):
        address = Web3.to_checksum_address(address)
        if address in self.attribs:
            if self.attribs[address]['category'] == 'token smart contract' or self.attribs[address]['category'] == 'smart contract' or self.attribs[address]['category'] == 'decentralized exchange':
                return True
        elif address in self.priv_addr_cache:
            return False
        else:
            if len(self.w3.eth.get_code(address)) > 0:
                self.attribs[address] = {'name':'unknown','category':'smart contract'}
                return True
            else:
                self.priv_addr_cache.add(address)
        return False
    
    def isService(self,address):
        address = Web3.to_checksum_address(address)
        if address in self.attribs:
            if self.attribs[address]['category'] == 'exchange' or self.attribs[address]['category'] == 'gambling' or self.attribs[address]['category'] == 'atm':
                return True
        elif address in self.priv_addr_cache:
            return False
        return False
