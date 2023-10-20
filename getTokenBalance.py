import argparse
from decimal import *
from etherscan import Etherscan
from web3 import Web3
import configparser
import json

#---------------------------
# Print out the token balance for a given address
def main():

    config = configparser.ConfigParser()
    config.read('/etc/chaintools.config')
    etherscan_api_key = config['keys']['EtherscanAPI']

    # json list of tokens stored locally of the format:
    #    "USDT": {
    #      "address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    #      "decimals": "lovelace"
    #    }
    token_contracts_file = config['locations']['TokenContracts']
    token_str = open(token_contracts_file).read()
    tokens = json.loads(token_str)

    args = parse_arguments()

    # make sure the address is in the checksum format
    address = args.address
    if not Web3.is_checksum_address(address):
        address = Web3.to_checksum_address(address)
    
    # you'll need an etherscan api key
    eth = Etherscan(etherscan_api_key)

    balance = ''

    # ETH is default, check to make sure no contract was passed in
    if args.token == 'ETH' and not args.contract:
        balance = eth.get_eth_balance(address)
        balance = Web3.from_wei(Decimal(balance), 'ether')
    # if a contract address was passed in get the balance for those tokens
    elif args.contract:
        contract = Web3.to_checksum_address(args.contract)
        # we won't know how many decimals the token supports
        balance = eth.get_acc_balance_by_token_and_contract_address(
            contract_address=contract,
            address=address)
    # if a token ticker was passed in check if we know the contract address
    elif args.token and args.token.upper() in tokens:
        contract = tokens[args.token.upper()]['address']
        balance = eth.get_acc_balance_by_token_and_contract_address(
            contract_address=contract,
            address=address)
        # decimals is basically what we have to multiple the value by to get a full token
        decimals = tokens[args.token.upper()]['decimals']
        balance = Web3.from_wei(Decimal(balance), decimals)
    elif not args.token in tokens:
        print("No contract mapping for {}, pass in contract address or update {}".format(args.token,token_contracts_file))
    
    print('{}'.format(balance))

#---------------------------
# parse arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
                    prog='ChainTools',
                    description='Scripts for manipulating transaction data',
                    epilog='happy hunting')
    parser.add_argument('-a', dest='address', action='store', required=False, help='address to get balance for')
    parser.add_argument('-c', dest='contract', action='store', required=False, help='contract address of the ERC20 token')
    parser.add_argument('-t', dest='token', action='store', required=False, default='ETH', help='token ticker of the ERC20 token')
    args = parser.parse_args()

    return args

if __name__ == "__main__":
    main()
