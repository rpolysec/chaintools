import json
import sys
import logging

logging.basicConfig(filename='taintedq.log', encoding='utf-8', level=logging.WARN)

class TaintedTokenQ:
    #-----------------------------
    # Initialize a new token queue
    def __init__(self, token):
        self.FundsQueue = []
        self.token = token

    def loadQ(self,q_json):
        # val consists of { 'tainted':boolean, 'value':'12345'}
        for val in q_json:
            self.FundsQueue.append(val)

    def toString(self):
        desc_str = '{} '.format(self.token)
        for val in self.FundsQueue:
            desc_str = '{} {} {}'.format(desc_str,val['tainted'],val['value'])
        return desc_str
    
    def toJson(self):
        return json.dumps(self.FundsQueue)

    #----------------------------
    # Process a credit from an unknown or legitimate source
    #
    # val : String representing the amount of tokens being added
    def processCredit(self,val):
        if len(self.FundsQueue) == 0:
            self.FundsQueue.append({'tainted':False, 'value':val})
        # the most recent funds in the queue are tainted, add untainted funds
        elif self.FundsQueue[len(self.FundsQueue)-1]['tainted']:
            self.FundsQueue.append({'tainted':False, 'value':val})
        # the most recent funds in the queue are not tainted, just add them together
        else:
            # the funds at the back of the queue aren't tainted, just add them to existing balance
            newvalue = int(self.FundsQueue[len(self.FundsQueue)-1]['value']) + int(val)
            self.FundsQueue[len(self.FundsQueue)-1]['value'] = str(newvalue)
        return int(val)
    
    #----------------------------
    # Process a known tainted credit. The credit can containt a mix 
    # of tainted and non-tainted funds, and the tainted credit object
    # contains a queue processed in order to make sure the right balances
    # are adjusted and the main funds queue is changed appropriately
    def processTaintedCredit(self,txn_q):

        t_credit = 0
        u_credit = 0

        for item in txn_q:
            if item['tainted']:
                t_credit = t_credit + int(item['value'])
                if len(self.FundsQueue) == 0 or not self.FundsQueue[len(self.FundsQueue)-1]['tainted']:
                    self.FundsQueue.append(item)
                elif self.FundsQueue[len(self.FundsQueue)-1]['tainted']:
                    newvalue = int(self.FundsQueue[len(self.FundsQueue)-1]['value']) + int(item['value'])
                    self.FundsQueue[len(self.FundsQueue)-1]['value'] =  str(newvalue)
            elif not item['tainted']:
                u_credit = u_credit + int(item['value'])
                if len(self.FundsQueue) == 0 or self.FundsQueue[len(self.FundsQueue)-1]['tainted']:
                    self.FundsQueue.append(item)
                elif not self.FundsQueue[len(self.FundsQueue)-1]['tainted']:
                    newvalue = int(self.FundsQueue[len(self.FundsQueue)-1]['value']) + int(item['value'])
                    self.FundsQueue[len(self.FundsQueue)-1]['value'] =  str(newvalue)
        return (t_credit,u_credit)
    
    # check if this debit will send tainted funds
    def isTaintedDebit(self,val):
        d_remain = int(val)
        if len(self.FundsQueue) == 0:
            return False
        
        # if the front of the queue is tainted then we just return true
        if self.FundsQueue[0]['tainted']:
            return True
        if not self.FundsQueue[0]['tainted'] and d_remain <= int(self.FundsQueue[0]['value']):
            return False
        
        # if we made it here subtract the first item amount from the value and check the next entry
        d_remain = d_remain - int(self.FundsQueue[0]['value'])
        if self.FundsQueue[1]['tainted'] and d_remain > 0:
            return True
        if not self.FundsQueue[1]['tainted'] and d_remain <= int(self.FundsQueue[1]['vake']):
            return False
        
        # if we made it here subtract the first item amount from the value and chedk the next entry
        d_remain = d_remain - int(self.FundsQueue[1]['value'])
        if self.FundsQueue[2]['tainted'] and d_remain > 0:
            return True
        if not self.FundsQueue[2]['tainted'] and d_remain <= int(self.FundsQueue[1]['vake']):
            return False
        
        # we should not make it here ever
        logging.error("IS TAINITED DEBIT COULD NOT RESOLVE PANIC val:{} q:{}".format(val,self.FundsQueue))
        sys.exit(0)

    #----------------------------
    # With every debit we have to ensure we follow any tainted funds
    # by creating a tainted transaction if tainted funds leave the address
    #
    # val : string representing amount of tokens being removed
    def processDebit(self,val):
        # grab the full value of the debit
        d_remain = int(val)
        t_debit = 0
        u_debit = 0
        # work through the queue until we run out of debit
        debit_q = []
        while d_remain > 0 and len(self.FundsQueue)>0:
            #print(debit_q)
            # we're removing more funds then what is at the front of the queue, this will pop
            if d_remain >= int(self.FundsQueue[0]['value']):
                d_remain = d_remain - int(self.FundsQueue[0]['value'])
                if self.FundsQueue[0]['tainted']:
                    t_debit = t_debit + int(self.FundsQueue[0]['value'])
                    debit_q.append({'tainted':True,'value':'{}'.format(self.FundsQueue[0]['value'])})
                    self.FundsQueue.pop(0)
                else:
                    u_debit = u_debit + int(self.FundsQueue[0]['value'])
                    debit_q.append({'tainted':False,'value':'{}'.format(self.FundsQueue[0]['value'])})
                    self.FundsQueue.pop(0)
            # this is the easy case, just subtract the value from what is in the front
            else:
                newvalue = int(self.FundsQueue[0]['value']) - d_remain
                self.FundsQueue[0]['value'] = str(newvalue)
                if self.FundsQueue[0]['tainted']:
                    t_debit = t_debit + d_remain
                    debit_q.append({'tainted':True,'value':'{}'.format(str(d_remain))})
                else:
                    u_debit = u_debit + d_remain
                    debit_q.append({'tainted':False,'value':'{}'.format(str(d_remain))})
                d_remain = 0
        return t_debit, u_debit, debit_q
    

##--------------
# UNIT TESTS
def main():
    testq = TaintedTokenQ('ETH')
    print(testq.toString())
    json_file = open('./TestData/testq1.json')
    json_str = json_file.read()
    testq1 = json.loads(json_str)
    testq.loadQ(testq1)
    print(testq.toString())
    testq.processCredit('50000000000000000000')
    print(testq.toString())
    testq.processCredit('50000000000000000000')
    print(testq.toString())
    testq.processDebit('5000000000')
    print(testq.toString())
    testq.processDebit('70000000000000000000000')
    print(testq.toString())

if __name__ == "__main__":
    main()
