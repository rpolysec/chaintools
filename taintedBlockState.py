from taintedAddressBalances import TaintedAddressBalances
from decimal import *
from os.path import exists
import json
from web3 import Web3
from sortedcontainers import SortedDict
from datetime import datetime
from taintedTokenBalance import TaintedTokenBalance

class TaintedBlockState:
    def __init__(self, blockNumber):
        self.blockNumber = blockNumber
        self.blockISODate = '0'
        self.taintedEOAs = {}
        self.taintedContracts = {}
        self.taintedServices = {}
        self.seedTaintedTxns = {}
        self.blockStateHistory = SortedDict()

    def loadState(self,jsonfile):
        # check if the file exists
        if not exists(jsonfile):
            print("file does not exist")
            return False
        
        json_str = json.loads(open(jsonfile).read())
        self.blockNumber = json_str['blockNumber']
        self.seedTaintedTxns = json_str['seedTaintedTxns']
        for ta in json_str['taintedEOAs']:
            self.taintedEOAs[ta['address']] = TaintedAddressBalances('0x0')
            self.taintedEOAs[ta['address']].loadTaintedAddressBalances(ta)
        for ta in json_str['taintedServices']:
            self.taintedServices[ta['address']] = TaintedAddressBalances('0x0')
            self.taintedServices[ta['address']].loadTaintedAddressBalances(ta)
        for ta in json_str['taintedContracts']:
            self.taintedContracts[ta['address']] = TaintedAddressBalances('0x0')
            self.taintedContracts[ta['address']].loadTaintedAddressBalances(ta)

    def toString(self):
        desc_str = '{}'.format(self.blockNumber)
        for ta in self.taintedEOAs:
            desc_str = '{}\n{}'.format(desc_str,self.taintedEOAs[ta].toString())
        return desc_str
    
    def addTaintedEOA(self,addr):
        if not addr in self.taintedEOAs:
            self.taintedEOAs[addr] = TaintedAddressBalances(addr)

    def addTaintedService(self,addr):
        if not addr in self.taintedServices:
            self.taintedServices[addr] = TaintedAddressBalances(addr)

    def addTaintedContract(self,addr):
        if not addr in self.taintedContracts:
            self.taintedContracts[addr] = TaintedAddressBalances(addr)
    
    def updateAddressName(self,addr,name):
        if addr in self.taintedEOAs:
            self.taintedEOAs[addr].name = name
        elif addr in self.taintedContracts:
            self.taintedContracts[addr].name = name
        elif addr in self.taintedServices:
            self.taintedServices[addr].name = name

    def updateAddressCategory(self,addr,category):
        if addr in self.taintedEOAs:
            self.taintedEOAs[addr].category = category
        elif addr in self.taintedContracts:
            self.taintedContracts[addr].category = category
        elif addr in self.taintedServices:
            self.taintedServices[addr].category = category

    def updateBlockNumber(self,blocknumber):
        self.blockNumber = blocknumber
    
    def updateBlockISODate(self,timestamp):
         self.blockISODate = datetime.fromtimestamp(timestamp).isoformat()

    # update the block history to save the state at a given point
    # in time
    def updateBlockHistory(self):
        # is this the latest block, if yes just write it as the history
        if len(self.blockStateHistory) == 0:
            self.blockStateHistory[self.blockNumber] = self.toJson()
        elif self.blockNumber > self.blockStateHistory.peekitem()[0]:
            self.blockStateHistory[self.blockNumber] = self.toJson()

    # check if processing this transaction would taint the receiver
    def isTaintedDebit(self,addr,token,value):
        return self.taintedEOAs[Web3.to_checksum_address(addr)].token_balances[token].isTaintedDebit(value)
    
    def addTokenToAddress(self,token,decimal,addr):
        addr = Web3.to_checksum_address(addr)
        if addr in self.taintedEOAs:
            if not token in self.taintedEOAs[addr].token_balances:
                self.taintedEOAs[addr].token_balances[token] = TaintedTokenBalance(token,int(decimal))
        elif addr in self.taintedServices:
            if not token in self.taintedServices[addr].token_balances:
                self.taintedServices[addr].token_balances[token] = TaintedTokenBalance(token,int(decimal))
        elif addr in self.taintedContracts:
            if not token in self.taintedContracts[addr].token_balances:
                self.taintedContracts[addr].token_balances[token] = TaintedTokenBalance(token,int(decimal))

    def processDebit(self,addr,token,value):
        addr = Web3.to_checksum_address(addr)
        t_debit, u_debit, q = self.taintedEOAs[addr].token_balances[token].processDebit(value)
        return t_debit, u_debit, q
    
    def processCredit(self,addr,token,q):
        addr = Web3.to_checksum_address(addr)
        t_credit = 0
        u_credit = 0
        if addr in self.taintedEOAs:
            t_credit, u_credit = self.taintedEOAs[addr].token_balances[token].processCredit(q)
        elif addr in self.taintedContracts:
            t_credit, u_credit = self.taintedContracts[addr].token_balances[token].processCredit(q)
        elif addr in self.taintedServices:
            t_credit, u_credit = self.taintedServices[addr].token_balances[token].processCredit(q)
        else:
            print('ADDRESS NOT IN ANY TAINTED LIST')
        return t_credit, u_credit
    
    def processGasDebit(self,addr,token,value):
        addr = Web3.to_checksum_address(addr)
        t_debit, u_debit, q = self.taintedEOAs[addr].token_balances[token].processDebit(value)
        self.taintedEOAs[addr].recordGas(t_debit)
        return t_debit, u_debit, q
    
    def getTokenBalances(self,addr):
        addr = Web3.to_checksum_address(addr)
        if addr in self.taintedEOAs:
            return self.taintedEOAs[addr].token_balances
        if addr in self.taintedContracts:
            return self.taintedContracts[addr].token_balances
        if addr in self.taintedServices:
            return self.taintedServices[addr].token_balances

    def toJson(self):
        ta_jsonstr = ''
        ta_services_jsonstr = ''
        ta_contracts_jsonstr = ''

        for ta in self.taintedEOAs:
            if ta_jsonstr == '':
                ta_jsonstr = '{}'.format(self.taintedEOAs[ta].toJson())
            else:
                ta_jsonstr = '{},\n{}'.format(ta_jsonstr,self.taintedEOAs[ta].toJson())

        for ta in self.taintedServices:
            if ta_services_jsonstr == '':
                ta_services_jsonstr = '{}'.format(self.taintedServices[ta].toJson())
            else:
                ta_services_jsonstr = '{},\n{}'.format(ta_services_jsonstr,self.taintedServices[ta].toJson())

        for ta in self.taintedContracts:
            if ta_contracts_jsonstr == '':
                ta_contracts_jsonstr = '{}'.format(self.taintedContracts[ta].toJson())
            else:
                ta_contracts_jsonstr = '{},\n{}'.format(ta_contracts_jsonstr,self.taintedContracts[ta].toJson())

        jsonstr = '{{"timeStamp":"{}","blockNumber":"{}", "seedTaintedTxns":[], "taintedServices":[\n{}\n], "taintedContracts":[\n{}\n], "taintedEOAs":[\n{}\n]}}'.format(self.blockISODate,self.blockNumber,ta_services_jsonstr,ta_contracts_jsonstr,ta_jsonstr)

        return jsonstr
    
    # check if there is a tainted txn q associated with this txn
    def getTaintedTxnQueue(self,txn):
        q = []
        if not 'dummy' in txn:
            for st in self.seedTaintedTxns:
                if st['txn']['blockNumber'] == txn['blockNumber'] and st['txn']['hash'] == txn['hash'] and st['txn']['value'] == txn['value'] and st['txn']['transactionIndex'] == txn['transactionIndex']:
                    q = st['queue']
        return q
    
    def isSeedTxn(self,txn):
        if not 'dummy' in txn:
            for st in self.seedTaintedTxns:
                if st['txn']['hash'] == txn['hash']:
                    return True
        return False
    
    def isTaintedEOA(self,addr):
        if Web3.to_checksum_address(addr) in self.taintedEOAs:
            return True
        return False
    
    def isTaintedAddr(self,addr):
        addr = Web3.to_checksum_address(addr)
        if addr in self.taintedEOAs or addr in self.taintedContracts or addr in self.taintedServices:
            return True
        return False
    
##--------------
# UNIT TESTS
def main():
    testq = TaintedBlockState('0')
    testq.loadState('./TestData/testbs.json')
    print(testq.toString())
    
    #testq.token_balances['ETH'].processCredit('50000000000000000000')
    #print(testq.toString())
    #testq.token_balances['ETH'].processCredit('50000000000000000000')
    #print(testq.toString())
    #testq.token_balances['ETH'].processDebit('5000000000')
    #print(testq.toString())
    #testq.token_balances['ETH'].processDebit('70000000000000000000000')
    #print(testq.toString())

if __name__ == "__main__":
    main()
