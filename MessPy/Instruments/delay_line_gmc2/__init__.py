import ctypes as ct
import os.path as osp
import time

import cffi

#ct.WinDLL('PI_GCS_DLL_x64')

#header = ''.join(open('PI_GCS2_DLL.h').readlines()[126:-3])
p = osp.dirname(__file__)
from pathlib import Path

cur_dir = Path(p)
if not Path(cur_dir/'C843_GCS_DLL_processed.h').exists():
    header = ''.join(open(p+'/C843_GCS_DLL.h').readlines()[104:299])
    header = header.replace('C843_FUNC_DECL', '')
    types = [('pi_uint8', 'uint8_t'),
             ('pi_int32', 'int32_t'),
             ('pi_int16', 'int16_t'),
             ('pi_uint16', 'uint16_t'),]
    for (x, y) in types:
        header = header.replace(x, y)
    header = header.replace('pi_int64', 'int64_t')
    file = Path(cur_dir / 'C843_GCS_DLL_processed.h').open('w')
    file.write(header)
else:
    header = ''.join(open(p + '/C843_GCS_DLL.h').readlines())
ffi = cffi.FFI()
ax = b'1'
ffi.cdef(header)
a = ffi.dlopen(p +'/C843_GCS_DLL_x64.dll')

board_idx = a.C843_Connect(1)
print(board_idx)
prefix = 'C843_'

bool_out = ffi.new('int[1]')
double_out = ffi.new('double[1]')

def void_func(func, con=board_idx, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)
    def func():
        a = fn(con, ax)
        return a
    return func

def bool_out_func(func, con=board_idx, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)
    def func():
        fn(con, ax, bool_out)
        return bool(bool_out[0])
    return func

def bool_in_func(func, con=board_idx, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)
    def func(b):
        out = fn(con, ax, [b])
        return bool(out)
    return func

def double_in_func(func, con=board_idx, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)
    def func(dbl):
        out = fn(con, ax, [dbl])
        return bool(out)
    return func

def double_out_func(func, con=board_idx, ax=ax, prefix=prefix):
    fn = getattr(a, prefix + func)
    def func():
        fn(con, ax, double_out)
        return double_out[0]
    return func

INI = void_func('INI')
#INI = lambda: a.C843_INI(i)
FNL = void_func('FNL')
FPL = void_func('FPL')
on_target = bool_out_func('qONT')
is_moving = bool_out_func('IsMoving')
is_ref_ok = bool_out_func('IsReferenceOK')
SVO = bool_in_func('SVO')
qSVO = bool_out_func('qSVO')
qFRF = bool_out_func('qFRF')
qREF = bool_out_func('qREF')

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

class DelayLine:
    def __init__(self, homepos=129.176):
        a.C843_CST(board_idx, ax, b"M-505.6PD")
        print(INI(), qSVO(), qFRF(), qREF(), is_ref_ok())
        #if not INI():
        #    raise IOError("Can't init C843")
        if not qSVO():
            print(SVO(True))
        if not is_ref_ok():
            print(FPL())
            while is_moving():
                print('ref ing')
                time.sleep(0.1)
        self.homepos = homepos
        self.move_mm(homepos, do_wait=False)

    def get_pos_mm(self):
        return qPOS()

    def get_pos_fs(self):
        return -mm_to_fs((self.get_pos_mm()-self.homepos)*2.)

    def move_mm(self, mm, do_wait=True):
        print(MOV(mm))
        if do_wait:
            while is_moving():
                print('mov ing')
                time.sleep(0.1)

    def move_fs(self, fs, do_wait=True):
        mm = -fs_to_mm(fs)
        print('mm', mm+self.homepos)
        self.move_mm(mm/2.+self.homepos, do_wait=do_wait)

    def set_speed(self, speed):
        speed = float(speed)
        return VEL(speed)

    def get_speed(self):
        return qVEL()

    def wait_until(self, pos):
        start_pos = self.get_pos_mm(self)
        diff = (pos - start_pos)
        if diff == 0:
            return
        sign = diff/abs(diff)
        while True:
            diff = (pos - start_pos)
            if sign*diff > 0:
                break

    def shutdown(self):
        a.C843_CloseConnection(board_idx)
dl = DelayLine()
#dl.set_speed(50.0)
#dl.move_mm(15.)
#dl.move_mm(150-130.)
