from abc import ABCMeta, abstractmethod

from evm.constants import TIME_BETWEEN_HEAD_HASH_SAVE
from eth_typing import (
    BlockNumber,
    Hash32,
    Address,
)

from evm.exceptions import InvalidHeadRootTimestamp


class BaseSchema(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def make_canonical_head_hash_lookup_key(wallet_address:Address) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_block_number_to_hash_lookup_key(wallet_address:Address, block_number: BlockNumber) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')

    @staticmethod
    @abstractmethod
    def make_transaction_hash_to_block_lookup_key(transaction_hash: Hash32) -> bytes:
        raise NotImplementedError('Must be implemented by subclasses')


class SchemaV1(BaseSchema):
    @staticmethod
    def make_canonical_head_hash_lookup_key(wallet_address:Address) -> bytes:
        return b'v1:canonical_head_hash:%s' % wallet_address
    
    @staticmethod
    def make_account_lookup_key(wallet_address:Address) -> bytes:
        return b'account:%s' % wallet_address

    @staticmethod
    def make_block_number_to_hash_lookup_key(wallet_address:Address, block_number: BlockNumber) -> bytes:
        number_to_hash_key = b'block-number-to-hash:%b-%d' % (wallet_address, block_number)
        return number_to_hash_key

    @staticmethod
    def make_transaction_hash_to_block_lookup_key(transaction_hash: Hash32) -> bytes:
        return b'transaction-hash-to-block:%s' % transaction_hash
    
    
    @staticmethod
    def make_current_head_root_lookup_key() -> bytes:
        return b'current-head-root'
    
    
    @staticmethod
    def make_historical_head_root_lookup_key() -> bytes:
        return b'historical-head-root-list'
    
    @staticmethod
    def make_head_root_for_timestamp_lookup_key(timestamp: int) -> bytes:
        #require that it is mod of 1000 seconds
        if timestamp % TIME_BETWEEN_HEAD_HASH_SAVE != 0:
            raise InvalidHeadRootTimestamp("Can only save or load head root hashes for timestamps in increments of {} seconds.".format(TIME_BETWEEN_HEAD_HASH_SAVE))
        return b'head-root-at-time:%i' % timestamp
    
    @staticmethod
    def make_block_hash_to_chain_wallet_address_lookup_key(block_hash: Hash32) -> bytes:
        return b'block-hash-to-chain-wallet-address:%b' % block_hash
    
    @staticmethod
    def make_chronological_window_lookup_key(timestamp: int) -> bytes:
        #require that it is mod of 1000 seconds
        if timestamp % TIME_BETWEEN_HEAD_HASH_SAVE != 0:
            raise InvalidHeadRootTimestamp("Can only save or load chronological block for timestamps in increments of {} seconds.".format(TIME_BETWEEN_HEAD_HASH_SAVE))
        return b'chronological-block-window:%i' % timestamp
    
    
    
    
    
    
