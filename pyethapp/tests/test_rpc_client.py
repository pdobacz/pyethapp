from pyethapp.jsonrpc import quantity_decoder
from pyethapp.rpc_client import JSONRPCClient


def test_find_block():
    JSONRPCClient.call = lambda self, cmd, num, flag: num
    client = JSONRPCClient()
    client.find_block(lambda x: x == '0x5')


def test_default_tx_gas():
    client = JSONRPCClient()
    genesis_block_info = client.call('eth_getBlockByNumber', 'earliest', False)
    genesis_gas_limit = quantity_decoder(genesis_block_info['gasLimit'])
    assert client.default_tx_gas == (genesis_gas_limit - 1)


def test_default_tx_gas_assigned():
    default_gas = 12345
    client = JSONRPCClient(default_tx_gas=default_gas)
    assert client.default_tx_gas == default_gas


def test_default_host():
    default_host = '127.0.0.1'
    client = JSONRPCClient()
    assert client.transport.endpoint == 'http://{}:{}'.format(default_host, client.port)


def test_set_host():
    host = '1.1.1.1'
    default_host = '127.0.0.1'
    client = JSONRPCClient(host)
    assert client.transport.endpoint == 'http://{}:{}'.format(host, client.port)
    assert client.transport.endpoint != 'http://{}:{}'.format(default_host, client.port)
