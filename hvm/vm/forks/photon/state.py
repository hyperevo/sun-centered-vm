from __future__ import absolute_import
from typing import Type  # noqa: F401

from hvm.vm.forks.photon.constants import REFUND_SELFDESTRUCT

from .account import PhotonAccountDB
from hvm.vm.forks.boson.state import BosonTransactionExecutor, BosonState

from .computation import PhotonComputation

from .transaction_context import PhotonTransactionContext

from .transactions import (
    PhotonTransaction,
    PhotonReceiveTransaction,
)
from typing import Union
from eth_utils import encode_hex
from eth_typing import Address
from typing import Optional

class PhotonTransactionExecutor(BosonTransactionExecutor):

    def get_transaction_context(self,
                                send_transaction: PhotonTransaction,
                                this_chain_address:Address,
                                receive_transaction: Optional[PhotonReceiveTransaction] = None,
                                refund_transaction: Optional[PhotonReceiveTransaction] = None) -> PhotonTransactionContext:

        if receive_transaction is None:
            is_receive = False
            receive_transaction_hash = None
        else:
            is_receive = True
            receive_transaction_hash = receive_transaction.hash

        if refund_transaction is None:
            is_refund = False
        else:
            is_refund = True

        return PhotonTransactionContext(
            origin=send_transaction.sender,
            gas_price=send_transaction.gas_price,
            send_tx_hash=send_transaction.hash,
            this_chain_address = this_chain_address,
            is_receive=is_receive,
            is_refund=is_refund,
            receive_tx_hash=receive_transaction_hash,
            tx_caller = send_transaction.caller if send_transaction.caller != b'' else None,
            tx_origin = send_transaction.origin if send_transaction.origin != b'' else None,
            tx_code_address = send_transaction.code_address if send_transaction.code_address != b'' else None,
            tx_signer = send_transaction.sender
        )

    def add_possible_refunds_to_currently_executing_transaction(self,
                                                                send_transaction: PhotonTransaction,
                                                                computation: PhotonComputation,
                                                                receive_transaction: PhotonReceiveTransaction = None,
                                                                refund_transaction: PhotonReceiveTransaction = None,
                                                                ) -> Union[PhotonTransaction, PhotonReceiveTransaction]:
        '''
        Receive transactions that have computation will have to refund any leftover gas. This refund amount depends
        on the computation which is why it is processed here and added the receive tx.

        :param send_transaction:
        :param computation:
        :param receive_transaction:
        :param refund_transaction:
        :return:
        '''
        if computation.transaction_context.is_refund:
            # this kind of receive transaction will always have 0 remaining refund so it doesnt need to be modified
            return refund_transaction

        elif computation.transaction_context.is_receive:
            # this kind of receive transaction may include a nonzero gas refund. Must add it in now
            # It gets a refund if send has data and is not create. ie. there was a computation on receive
            if computation.transaction_context.is_computation_call_origin or (computation.msg.data != b'' and not computation.msg.is_create):
                # New: we always process refunds after receiving a transaction originating in a computation call
                if computation.has_external_call_messages and not computation.is_error:
                    # If the computation has child transactions that it must make, and there were no errors, then save the gas to send them.
                    # But if there was an error, then we still return whatever gas is left over like normal, which is the else.

                    self.vm_state.logger.debug(
                        'SAVING REFUND FOR CHILD CALLS: tx_hash = {}'.format(receive_transaction.hash)
                    )
                else:

                    gas_refund_amount = computation.get_gas_remaining_including_refunds()

                    self.vm_state.logger.debug(
                        'SAVING REFUND TO RECEIVE TX: %s -> %s',
                        gas_refund_amount,
                        encode_hex(computation.msg.sender),
                    )
                    receive_transaction = receive_transaction.copy(remaining_refund=gas_refund_amount)

            return receive_transaction
        else:
            # this is a send transaction. Refunds are only possible on receive tx. So send it back unmodified
            return send_transaction

    def finalize_computation(self, send_transaction: PhotonTransaction, computation: PhotonComputation) -> PhotonComputation:
        #we only have to do any of this if it is a send transaction

        # Self Destruct Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.refund_gas(REFUND_SELFDESTRUCT * num_deletions)


        if not computation.transaction_context.is_receive and not computation.transaction_context.is_refund and not computation.transaction_context.is_computation_call_origin:
            # this is a send transaction that didnt originate from a computation call. This is the only kind that could potentially refund gas

            if computation.msg.is_create or computation.msg.data == b'':
                # We are deploying a smart contract, we pay all computation fees now and refund leftover gas
                # OR
                # This transaction has no computation. It is just a HLS transaction. Send the transaction and refund leftover gas

                gas_remaining = computation.get_gas_remaining()
                gas_refunded = computation.get_gas_refund()

                gas_used = send_transaction.gas - gas_remaining
                gas_refund = min(gas_refunded, gas_used // 2)
                gas_refund_amount = (gas_refund + gas_remaining) * send_transaction.gas_price

                if gas_refund_amount:
                    self.vm_state.logger.debug(
                        'GAS REFUND: %s -> %s',
                        gas_refund_amount,
                        encode_hex(computation.msg.sender),
                    )

                    self.vm_state.account_db.delta_balance(computation.msg.sender, gas_refund_amount)

                # In order to keep the state consistent with the block headers, we want the newly created smart contract chain
                # to have an empty state. The smart contract data will be stored when the recieve transaction is executed.
                # At that time, the smart contract state can also be saved in the block header to keep the local state and
                # block header state consistent at all times.

                # This is also in line with the policy to only run computation on recieve transactions.

class PhotonState(BosonState):
    computation_class: Type[PhotonComputation] = PhotonComputation
    transaction_executor: Type[PhotonTransactionExecutor] = PhotonTransactionExecutor
    account_db_class: Type[PhotonAccountDB] = PhotonAccountDB
    transaction_context_class: Type[PhotonTransactionContext] = PhotonTransactionContext

    account_db: PhotonAccountDB = None
    
