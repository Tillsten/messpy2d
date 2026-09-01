"""
Created on Mon Oct 12 22:11:01 2020

@author: tills
"""


import pydffi

ffi = pydffi.FFI()
dll = pydffi.dlopen(r'C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLDFM_64.dll')
tldfm = ffi.cdef(r'#include "C:\Program Files\IVI Foundation\VISA\Win64\Include\TLDFM.h"')

# %%
handle = tldfm.types.ViSession(0)
count = tldfm.types.ViUInt32(0)
tldfm.funcs.TLDFM_get_device_count(handle, pydffi.ptr(count))