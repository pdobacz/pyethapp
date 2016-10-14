from itertools import count
import gevent
import gc

import pytest
import ethereum
import ethereum.config
import ethereum.keys
from ethereum.ethpow import mine
from ethereum import tester
from ethereum.slogging import get_logger
from devp2p.peermanager import PeerManager
import ethereum._solidity

from pyethapp.accounts import Account, AccountsService, mk_random_privkey
from pyethapp.app import EthApp
from pyethapp.config import update_config_with_defaults, get_default_config
from pyethapp.db_service import DBService
from pyethapp.eth_service import ChainService
from pyethapp.jsonrpc import JSONRPCServer
from pyethapp.profiles import PROFILES
from pyethapp.pow_service import PoWService


log = get_logger('test.jsonrpc')


@pytest.fixture(params=[0,
    PROFILES['testnet']['eth']['block']['ACCOUNT_INITIAL_NONCE']])
def test_app(request, tmpdir):

    class TestApp(EthApp):

        def start(self):
            super(TestApp, self).start()
            log.debug('adding test accounts')
            # high balance account
            self.services.accounts.add_account(Account.new('', tester.keys[0]), store=False)
            # low balance account
            self.services.accounts.add_account(Account.new('', tester.keys[1]), store=False)
            # locked account
            locked_account = Account.new('', tester.keys[2])
            locked_account.lock()
            self.services.accounts.add_account(locked_account, store=False)
            assert set(acct.address for acct in self.services.accounts) == set(tester.accounts[:3])

        def mine_next_block(self):
            """Mine until a valid nonce is found.

            :returns: the new head
            """
            log.debug('mining next block')
            block = self.services.chain.chain.head_candidate
            delta_nonce = 10 ** 6
            for start_nonce in count(0, delta_nonce):
                bin_nonce, mixhash = mine(block.number, block.difficulty, block.mining_hash,
                                          start_nonce=start_nonce, rounds=delta_nonce)
                if bin_nonce:
                    break
            self.services.pow.recv_found_nonce(bin_nonce, mixhash, block.mining_hash)
            log.debug('block mined')
            assert self.services.chain.chain.head.difficulty == 1
            return self.services.chain.chain.head

        def rpc_request(self, method, *args):
            """Simulate an incoming JSON RPC request and return the result.

            Example::

                >>> assert test_app.rpc_request('eth_getBalance', '0x' + 'ff' * 20) == '0x0'

            """
            log.debug('simulating rpc request', method=method)
            method = self.services.jsonrpc.dispatcher.get_method(method)
            res = method(*args)
            log.debug('got response', response=res)
            return res

    config = {
        'data_dir': str(tmpdir),
        'db': {'implementation': 'EphemDB'},
        'pow': {'activated': False},
        'p2p': {
            'min_peers': 0,
            'max_peers': 0,
            'listen_port': 29873
        },
        'node': {'privkey_hex': mk_random_privkey().encode('hex')},
        'discovery': {
            'boostrap_nodes': [],
            'listen_port': 29873
        },
        'eth': {
            'block': {  # reduced difficulty, increased gas limit, allocations to test accounts
                'ACCOUNT_INITIAL_NONCE': request.param,
                'GENESIS_DIFFICULTY': 1,
                'BLOCK_DIFF_FACTOR': 2,  # greater than difficulty, thus difficulty is constant
                'GENESIS_GAS_LIMIT': 3141592,
                'GENESIS_INITIAL_ALLOC': {
                    tester.accounts[0].encode('hex'): {'balance': 10 ** 24},
                    tester.accounts[1].encode('hex'): {'balance': 1},
                    tester.accounts[2].encode('hex'): {'balance': 10 ** 24},
                }
            }
        },
        'jsonrpc': {'listen_port': 4488, 'listen_host': '127.0.0.1'}
    }
    services = [DBService, AccountsService, PeerManager, ChainService, PoWService, JSONRPCServer]
    update_config_with_defaults(config, get_default_config([TestApp] + services))
    update_config_with_defaults(config, {'eth': {'block': ethereum.config.default_config}})
    app = TestApp(config)
    for service in services:
        service.register_with_app(app)

    def fin():
        log.debug('stopping test app')
        for service in app.services:
            gevent.sleep(.1)
            try:
                app.services[service].stop()
            except Exception as e:
                log.DEV(str(e), exc_info=e)
                pass
        app.stop()
        gevent.killall(task for task in gc.get_objects() if isinstance(task, gevent.Greenlet))

    request.addfinalizer(fin)

    log.debug('starting test app')
    app.start()
    return app
