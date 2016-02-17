import unittest
import time

import pytest
from requests import ConnectionError

from pyethapp.rpc_client import JSONRPCClient


def test_find_block():
    JSONRPCClient.call = lambda self, cmd, num, flag: num
    client = JSONRPCClient()
    client.find_block(lambda x: x == '0x5')


class TestJSONRPCClient(unittest.TestCase):
    def setUp(self):
        self.test_output = []
        self.test_successful = False
        self.connect_client()

    def log(self, msg):
        msg = '{} {}'.format(time.time(), msg)
        self.test_output.append(msg)

    def wait_for_new_block(self, timeout=0):
        start_ts = time.time()
        while True:
            self.log('wait_for_new_block')
            block_hashes = self.client.call('eth_getFilterChanges', self.new_block_filter_id)
            if block_hashes:
                return block_hashes[0]
            if timeout and time.time() - start_ts > timeout:
                return None
            time.sleep(0.5)

    def connect_client(self):
        while True:
            try:
                self.client = JSONRPCClient()
                self.client.call('web3_clientVersion')
                break
            except ConnectionError:
                time.sleep(0.5)

    def test_eth_sendTransaction_contract_depoly(self):
        try:
            # Compile the contract
            import ethereum._solidity
            s = ethereum._solidity.get_solidity()
            if s is None:
                pytest.xfail("solidity not installed, not tested")
            else:
                solidity_code = "contract testContract { function power(uint a) returns(uint d) { return a * a; } }"
                contract_binary = s.compile(solidity_code)

                # Set up filter to get notified when a new block arrives
                self.new_block_filter_id = self.client.call('eth_newBlockFilter')

                # Create a contract
                tx_hash = self.client.eth_sendTransaction(sender=self.client.coinbase, to='', data=contract_binary)
                self.log('After send transaction, tx_hash={}'.format(tx_hash))

                # Wait for new block
                recent_block_hash = self.wait_for_new_block()
                recent_block = self.client.call('eth_getBlockByHash', recent_block_hash, True)
                self.log('New block {} mined'.format(recent_block))

                # Is the transaction in block?
                assert len(recent_block['transactions']) == 0
                tx = recent_block['transactions'][0]
                assert tx['hash'] == tx_hash
                self.log('The transaction exists in the most recent block')

                # Get transaction receipt
                receipt = self.client.call('eth_getTransactionReceipt', tx_hash)
                self.log('The transaction receipt: {}'.format(receipt))

                assert receipt['transactionHash'] == tx['hash']
                assert receipt['blockHash'] == tx['blockHash']
                assert receipt['blockHash'] == recent_block['hash']

                # Get contract address from receipt
                contract_address = receipt['contractAddress']
                self.log('The contract address is {}'.format(contract_address))
                code = self.client.call('eth_getCode', contract_address)
                self.log('eth_getCode returned {}'.format(code))

                assert code.startswith('0x')
                assert len(code) > len('0x')
                self.test_successful = True
                assert self.test_successful, '\n'.join(self.test_output)

        except Exception, e:
            self.log(unicode(e))
