import logging

from hvm.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from hvm.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_is_integer,
    validate_gte,
    validate_uint256,
    validate_is_boolean,
)

from eth_typing import Address

class Message(object):
    """
    A message for VM computation.
    resolved_to resolves CREATE_CONTRACT_ADDRESS to the actual contract address
    """
    __slots__ = [
        'to', 'sender', 'value', 'data', 'depth', 'gas', 'code', '_code_address',
        'create_address', 'should_transfer_value', 'is_static', 'refund_amount',
        'execute_on_send', 'nonce'
    ]

    logger = logging.getLogger('hvm.vm.message.Message')

    def __init__(self,
                 gas,
                 to,
                 sender,
                 value,
                 data,
                 code,
                 depth=0,
                 create_address=None,
                 code_address=None,
                 should_transfer_value=True,
                 is_static=False,
                 refund_amount=0,
                 execute_on_send=False,
                 nonce=0):
        validate_uint256(gas, title="Message.gas")
        self.gas = gas  # type: int

        if to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(to, title="Message.to")

        self.to = to

        validate_canonical_address(sender, title="Message.sender")
        self.sender = sender

        validate_uint256(value, title="Message.value")
        self.value = value

        validate_uint256(nonce, title="Message.nonce")
        self.nonce = nonce

        validate_is_bytes(data, title="Message.data")
        self.data = data

        validate_is_integer(depth, title="Message.depth")
        validate_gte(depth, minimum=0, title="Message.depth")
        self.depth = depth

        validate_is_bytes(code, title="Message.code")
        self.code = code

        if create_address is not None:
            validate_canonical_address(create_address, title="Message.create_address")
        self.create_address = create_address

        if code_address is not None:
            validate_canonical_address(code_address, title="Message.code_address")
        self.code_address = code_address

        validate_is_boolean(should_transfer_value, title="Message.should_transfer_value")
        self.should_transfer_value = should_transfer_value

        validate_is_integer(depth, title="Message.refund_amount")
        self.refund_amount = refund_amount

        validate_is_boolean(is_static, title="Message.is_static")
        self.is_static = is_static

        validate_is_boolean(execute_on_send, title="Message.execute_on_send")
        self.execute_on_send = execute_on_send


    @property
    def code_address(self):
        if self._code_address is not None:
            return self._code_address
        else:
            return self.to

    @code_address.setter
    def code_address(self, value):
        self._code_address = value


    @property
    def resolved_to(self):
        # previously called storage address
        if self.create_address is not None:
            return self.create_address
        else:
            return self.to

    @property
    def is_create(self):
        return self.to == CREATE_CONTRACT_ADDRESS or self.create_address is not None

    @property
    def data_as_bytes(self) -> bytes:
        return bytes(self.data)



