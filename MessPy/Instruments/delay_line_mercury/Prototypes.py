'''
Created on 27.07.2011

@author: cwu
'''
import ctypes as C


def Int_as_arg(function):
    function.argtypes = [C.c_int]
    
def IntInt_as_arg_Int_as_ret(function):
    function.argtypes = [C.c_int,C.c_int]
    function.restype = C.c_int

def CharBuffWithLenConstCharArr_as_arg_Long_as_ret(function):
    function.argtypes = [C.c_char_p,C.c_int,C.c_char_p]
    function.restype = C.c_int
  

def ConstCharArr_as_arg_Long_as_ret(function):
    function.argtypes = [C.c_char_p]
    function.restype = C.c_int

def LongConstCharArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p]
    function.restype = C.c_int

def LongCharBuffWithLen_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.c_int]
    function.restype = C.c_int

def LongConstCharArrLongArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int)]
    function.restype = C.c_int

def LongConstIntArrLongArrInt_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_int),C.c_int]
    function.restype = C.c_int

def LongConstCharArrDoubleArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_double)]
    function.restype = C.c_int

def LongConstCharArrLongArrLongArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int),C.POINTER(C.c_int)]
    function.restype = C.c_int
    
def LongInt8Int8Int16Int32(function):
    function.argtypes = [C.c_int,C.c_int8,C.c_int8,C.c_int16,C.c_int32]
    function.restype = C.c_int
    
def LongInt8Int8Int16Int32Ptr(function):
    function.argtypes = [C.c_int,C.c_int8,C.c_int8,C.c_int16,C.POINTER(C.c_int32)]
    function.restype = C.c_int

def LongInt8Int8Int32(function):
    function.argtypes = [C.c_int,C.c_int8,C.c_int8,C.c_int32]
    function.restype = C.c_int
    
def LongInt8Int8Int32Ptr(function):
    function.argtypes = [C.c_int,C.c_int8,C.c_int8,C.POINTER(C.c_int32)]
    function.restype = C.c_int

def LongConstCharArrLongArrDoubleArrCharArrWithBuffLen_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int), C.POINTER(C.c_double), C.c_char_p, C.c_int]
    function.restype = C.c_int
    
    
def LongConstCharArrConstLongArrConstDoubleArrConstCharArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int), C.POINTER(C.c_double), C.c_char_p]
    function.restype = C.c_int
    
#SPA_String    
def LongConstCharArrConstLongArrConstCharArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int), C.c_char_p]

def LongLongArr_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int, C.POINTER(C.c_int)]
    function.restype = C.c_int

#qSPA_String      
def LongConstCharArrLongArrCharArrWithBuffLen_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.c_char_p,C.POINTER(C.c_int), C.c_char_p, C.c_int]
    function.restype = C.c_int

def LongConstIntArrCharBuffWithLenInt_as_arg_BOOL_as_ret(function):
    function.argtypes = [C.c_int,C.POINTER(C.c_int), C.c_char_p, C.c_int, C.c_int]
    function.restype = C.c_int

