from nicelib import load_lib

a = load_lib("pi", __package__)

print(a._argnames)
from nicelib import NiceLib, NiceObject, RetHandler, Sig, load_lib, ret_ignore


@RetHandler(num_retvals=0)
def ret_errcode(retval, niceobj):
    if retval != 0:
        raise niceobj.error_message(retval)


class PIController(NiceLib):
    _info_ = load_lib("pi", __package__)
    # _ret_ = ret_errcode
    _prefix_ = "PI_"

    # get_device_count = Sig("in", "out")
    # get_device_configuration (ViSession instrumentHandle, ViPUInt32 segmentCnt, ViPReal64
    # minSegementVoltage, ViPReal64 maxSegmentVoltage, ViPReal64 segmentCommonVoltageMax, ViPUInt32 tiltElementCnt, ViPReal64 minTiltVoltage, ViPReal64 maxTiltVoltage, ViPReal64 tiltCommonVoltageMax);

    #init = Sig("in", "in", "in", "out")

    class Mirror(NiceObject):
        _init_ = "init"
