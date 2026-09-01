import ctypes as ct
import os.path as osp
import time

import cffi

from MessPy.Instruments.interfaces import IDelayLine

# ct.WinDLL('PI_GCS_DLL_x64')

#header = ''.join(open('PI_GCS2_DLL.h').readlines()[126:-3])
p = osp.dirname(__file__)
header = ''.join(open(p+'/PI_GCS2_DLL.h').readlines()[126:300])
header = header.replace('PI_FUNC_DECL', '')
header = header.replace('__int64', 'int64_t')

ffi = cffi.FFI()
ax = b'1'
ffi.cdef(header)
a = ffi.dlopen(p + '/PI_GCS2_DLL_x64.dll')
i = a.PI_ConnectUSB(b'0145500652')
prefix = 'PI_'

bool_out = ffi.new('int[1]')
double_out = ffi.new('double[1]')


def void_func(func, con=i, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)

    def func():
        a = fn(con, ax)
        return a
    return func


def bool_out_func(func, con=i, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)

    def func():
        fn(con, ax, bool_out)
        return bool(bool_out[0])
    return func


def bool_in_func(func, con=i, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)

    def func(b):
        out = fn(con, ax, [b])
        return bool(out)
    return func


def double_in_func(func, con=i, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)

    def func(dbl):
        out = fn(con, ax, [dbl])
        return bool(out)
    return func


def double_out_func(func, con=i, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)

    def func():
        fn(con, ax, double_out)
        return double_out[0]
    return func


INI = void_func('INI')
FNL = void_func('FNL')
SVO = bool_in_func('SVO')
on_target = bool_out_func('qONT')
is_moving = bool_out_func('IsMoving')
qSVO = bool_out_func('qSVO')
qFRF = bool_out_func('qFRF')
qPOS = double_out_func('qPOS')
qVEL = double_out_func('qVEL')
VEL = double_in_func('VEL')
MOV = double_in_func('MOV')


def mm_to_fs(pos_in_mm):
    "converts mm to femtoseconds"
    speed_of_light = 299792458.
    pos_in_meters = pos_in_mm / 1000.
    pos_sec = pos_in_meters / speed_of_light
    return pos_sec * 1e15


def fs_to_mm(t_fs):
    speed_of_light = 299792458.
    pos_m = speed_of_light * t_fs * 1e-15
    return pos_m * 1000.


class DelayLine(IDelayLine):
    def __init__(self):
        self.pos_sign = -1
        # if not INI():
        #    raise IOError("Can't init Mercury")
        if not qSVO():
            print(SVO(True))
        if not qFRF():
            print(FNL)
            while is_moving():
                print('ref ing')
                time.sleep(0.1)
        self.set_speed(6.0)

        try:
            with open('zeropos', 'r') as f:
                self.home_pos = float(f.readline())
        except OSError:
            self.home_pos = 9.0

    def get_pos_mm(self):
        return qPOS()

    def get_mm(self):
        return qPOS()

    def move_mm(self, mm, do_wait=True):
        a = MOV(mm)
        if do_wait:
            while is_moving():
                #print('mov ing')
                time.sleep(0.05)
        return a

    def set_speed(self, speed):
        speed = float(speed)
        return VEL(speed)

    def get_speed(self):
        return qVEL()

    def wait_unil(self, pos):
        start_pos = self.get_pos_mm(self)
        diff = (pos - start_pos)
        if diff == 0:
            return
        sign = diff/abs(diff)
        while True:
            diff = (pos - start_pos)
            if sign*diff > 0:
                break

    def is_moving(self):
        return is_moving()

    def def_home(self):
        self.home_pos = self.get_pos_mm()
        with open('zeropos', 'w') as f:
            f.writelines(str(self.home_pos))
        return self.home_pos

    def get_home(self):
        return self.home_pos


_dl = DelayLine()

if __name__ == '__main__':
    import xmlrpc.server

    server = xmlrpc.server.SimpleXMLRPCServer(('', 8000))
    server.register_instance(dl)
    server.serve_forever()

# dl.move_mm(15)
# dl.move_mm(0)
