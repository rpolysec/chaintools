from taintedTokenQ import TaintedTokenQ
from decimal import *
import json

class TaintedTokenBalance:
    #-----------------------------
    # Initialize a new token queue
    def __init__(self, token, decimal):
        self.token = token
        self.decimal = decimal
        self.Balance = 0
        self.TBalance = 0
        self.UBalance = 0
        self.taintedQ = TaintedTokenQ(token)

    def loadTokenBalance(self, tb_json):
        self.token = tb_json['token']
        self.decimal = int(tb_json['decimal'])
        self.Balance = int(tb_json['balance'])
        self.TBalance = int(tb_json['tbalance'])
        self.UBalance = int(tb_json['ubalance'])
        self.taintedQ.loadQ(tb_json['queue'])

    # This could either be a queue of tainted funds
    # from an unknown source, or a queue of funds
    # resulting from a swap of tainted tokens. We trace
    # the result of the swap coming back.
    def processCredit(self,txnq):
        TCredit, UCredit = self.taintedQ.processTaintedCredit(txnq)
        self.TBalance = self.TBalance + TCredit
        self.UBalance = self.UBalance + UCredit
        self.Balance = self.Balance + TCredit + UCredit
        return TCredit, UCredit

    # check if this debit would results in sending funds
    # to a new address. This effectively taints the new
    # address, so we have to handle that upstream
    def isTaintedDebit(self,val):
        return self.taintedQ.isTaintedDebit(val)

    # If the debit contains all or partial tainted funds
    # then we'll get back a queue representing the funds
    # we want to follow. This is different from a swap where
    # we don't want to follow the debit'd funds and instead
    # follow the asset that it was exchanged for
    def processDebit(self,val):
        TDebit, UDebit, q = self.taintedQ.processDebit(val)
        self.TBalance = self.TBalance - TDebit
        self.UBalance = self.UBalance - UDebit
        self.Balance = self.Balance - TDebit - UDebit
        return TDebit, UDebit, q

    # A very simple case where tokens are coming in and they
    # are not the result of a tainted swap or tainted deposit
    def processCreditDeprecated(self,val):
        UCredit = self.taintedQ.processCredit(val)
        self.Balance = self.Balance + UCredit
        self.UBalance = self.UBalance + UCredit

    # Relatively simple, call the taintedQ with the amount
    # of gas to subtract. We don't trace gas, so it funds
    # we cannot recover. But if the gas came from tainted
    # funds we account for the difference.
    def processGas(self,val):
        TDebit, UDebit = self.taintedQ.processDebit(val)
        self.TBalance = self.TBalance - TDebit
        self.UBalance = self.UBalance - UDebit
        self.Balance = self.Balance - TDebit - UDebit
        # let the caller know how much gas was tainted
        return TDebit

    # format a balance into something human readable
    # based on this tokens decimals
    def valToString(self,val):
        val = Decimal(val)
        for i in range(0,int(self.decimal)):
            val = val/Decimal(10.0)
        return '{:.4f}'.format(val)

    # human friendly summary of the balances for this token
    def toString(self):
        if self.Balance < 2:
            return ''
        
        b = Decimal(self.Balance)
        for i in range(0,self.decimal):
            b = b/Decimal(10.0)

        tb = Decimal(self.TBalance)
        for i in range(0,self.decimal):
            tb = tb/Decimal(10.0)

        ub = Decimal(self.UBalance)
        for i in range(0,self.decimal):
            ub = ub/Decimal(10.0)

        if len(self.token) > 10:
            return '{},{:.4f},{:.4f},{:.4f}'.format('SCAM', b, tb, ub)
        
        return '{},{:.4f},{:.4f},{:.4f}'.format(self.token, b, tb, ub)
    
    # json formatted blances for this token
    def toJson(self):
        return '{{"token":"{}", "decimal":"{}", "tbalance":"{}", "ubalance":"{}", "balance":"{}", "queue":{}}}'.format(self.token,self.decimal,self.TBalance,self.UBalance,self.Balance,self.taintedQ.toJson())

##--------------
# UNIT TESTS
def main():
    testq = TaintedTokenBalance('ETH',18)
    print(testq.toString())
    json_file = open('./TestData/testtb.json')
    json_str = json_file.read()
    testtb = json.loads(json_str)
    testq.loadTokenBalance(testtb)
    print(testq.toString())
    
    testq.processCredit('50000000000000000000')
    print(testq.toString())
    print(testq.taintedQ.toString())
    testq.processCredit('50000000000000000000')
    print(testq.toString())
    print(testq.taintedQ.toString())
    testq.processDebit('5000000000')
    print(testq.toString())
    print(testq.taintedQ.toString())
    testq.processDebit('70000000000000000000000')
    print(testq.toString())
    print(testq.taintedQ.toString())

if __name__ == "__main__":
    main()
