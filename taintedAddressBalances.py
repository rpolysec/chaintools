from taintedTokenBalance import TaintedTokenBalance
import json
from decimal import *

class TaintedAddressBalances:

    #-----------------------------
    # Initialize a new Tainted Address Balances object
    # that trackes ETH and ERC20 token balances associated
    # with a crypto address.
    def __init__(self,address):
        self.address = address
        self.name = 'none'
        self.category = 'none'
        self.token_balances = {}
        self.tainted_gas = 0

    def loadTaintedAddressBalances(self,ta_json):
        self.address = ta_json['address']
        for tb in ta_json['tokenstates']:
            if not tb['token'] in self.token_balances:
                self.token_balances[tb['token']] = TaintedTokenBalance(tb['token'],int(tb['decimal']))
                self.token_balances[tb['token']].loadTokenBalance(tb)
    
    # keep track of how much "tainted" gas this address has spent
    # over time some stolen funds will naturally be spent on gas
    # which isn't really recoverable
    def recordGas(self,value):
        self.tainted_gas+=int(value)

    def toString(self):
        desc_str = '{}'.format(self.address)
        for tb in self.token_balances:
            desc_str = '{} {}'.format(desc_str,self.token_balances[tb].toString())
        return desc_str

    def toJson(self):
        tb_jsonstr = ''
        for tb in self.token_balances:
            if len(self.token_balances[tb].token) < 8:
                if tb_jsonstr == '':
                    tb_jsonstr = '{}'.format(self.token_balances[tb].toJson())
                else:
                    tb_jsonstr = '{},\n{}'.format(tb_jsonstr,self.token_balances[tb].toJson())
        return '{{"address":"{}", "name":"{}", "category":"{}", "tokenstates":[\n{}\n]}}'.format(self.address,self.name,self.category,tb_jsonstr)

##--------------
# UNIT TESTS
def main():
    testq = TaintedAddressBalances('0x0')
    print(testq.toString())
    json_file = open('./TestData/testta.json')
    json_str = json_file.read()
    testtb = json.loads(json_str)
    testq.loadTaintedAddressBalances(testtb)
    print(testq.toString())
    
    testq.token_balances['ETH'].processCredit('50000000000000000000')
    print(testq.toString())
    testq.token_balances['ETH'].processCredit('50000000000000000000')
    print(testq.toString())
    testq.token_balances['ETH'].processDebit('5000000000')
    print(testq.toString())
    testq.token_balances['ETH'].processDebit('70000000000000000000000')
    print(testq.toString())

if __name__ == "__main__":
    main()
