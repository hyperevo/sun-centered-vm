from py_ecc import (
    optimized_bn128 as bn128,
)

from hvm import constants
from hvm.exceptions import (
    ValidationError,
    VMError,
)
from hvm.utils.bn128 import (
    validate_point,
)
from hvm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from hvm.utils.padding import (
    pad32,
    pad32r,
)
from eth_utils.toolz import (
    curry,
)

from typing import TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from hvm.vm.forks.photon import PhotonComputation

@curry
def ecadd(
        computation: 'PhotonComputation',
        gas_cost: int = constants.GAS_ECADD) -> 'PhotonComputation':

    computation.consume_gas(gas_cost, reason='ECADD Precompile')

    try:
        result = _ecadd(computation.msg.data_as_bytes)
    except ValidationError:
        raise VMError("Invalid ECADD parameters")

    result_x, result_y = result
    result_bytes = b''.join((
        pad32(int_to_big_endian(result_x.n)),
        pad32(int_to_big_endian(result_y.n)),
    ))
    computation.output = result_bytes
    return computation


def _ecadd(data: bytes) -> Tuple[bn128.FQ, bn128.FQ]:
    x1_bytes = pad32r(data[:32])
    y1_bytes = pad32r(data[32:64])
    x2_bytes = pad32r(data[64:96])
    y2_bytes = pad32r(data[96:128])

    x1 = big_endian_to_int(x1_bytes)
    y1 = big_endian_to_int(y1_bytes)
    x2 = big_endian_to_int(x2_bytes)
    y2 = big_endian_to_int(y2_bytes)

    p1 = validate_point(x1, y1)
    p2 = validate_point(x2, y2)

    result = bn128.normalize(bn128.add(p1, p2))
    return result



