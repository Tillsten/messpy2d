from nicelib import load_lib

a = load_lib('tldfm', __package__)

print(a._argnames)
from nicelib import NiceLib, NiceObject, RetHandler, Sig, load_lib, ret_ignore


@RetHandler(num_retvals=0)
def ret_errcode(retval):
    if retval != 0:
        raise MotorError(NiceMotor.GetErrorString(retval))

class DFM(NiceLib):
    _info_ = load_lib('tldfm', __package__)
    #_ret_ = ret_errcode
    _prefix_ = 'TLDFM_'

    get_device_count = Sig('in', 'out')
    init = Sig('in', 'in', 'in', 'out')

    class Mirror(NiceObject):
        _init_ = 'init'
        close = Sig('in')
        reset = Sig('in')
        self_test = Sig('in', 'out', 'buf[50]')

        get_voltages = Sig('in', 'arr[5]', 'arr[50]' )
