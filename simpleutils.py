import argparse
from decimal import *
from etherscan import Etherscan
from web3 import Web3

etherscan_api_key = '<your etherscan api key>'

#---------------------------
# Print out the ethereum balance for a given address
def main():

    args = parse_arguments()

    if args.address:
        # make sure we're always dealing with checksum version of addresses
        address = args.address
        if not Web3.is_checksum_address(address):
            address = Web3.to_checksum_address(address)

        eth = Etherscan(etherscan_api_key)
        result = eth.get_eth_balance(address)
        result = Web3.from_wei(Decimal(result), 'ether')
        print(result)

#---------------------------
# parse arguments
def parse_arguments():
    parser = argparse.ArgumentParser(
                    prog='ChainTools',
                    description='Scripts for manipulating transaction data',
                    epilog='happy hunting')
    parser.add_argument('-a', dest='address', action='store', required=False, help='address to get ETH balance for')
    args = parser.parse_args()

    return args

if __name__ == "__main__":
    main()
