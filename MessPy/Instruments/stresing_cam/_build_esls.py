"""
Created on Thu Feb 28 12:18:10 2019

@author: localadmin
"""

# _build_foo.py
from nicelib import build_lib

header_info = {
    'win*': {
        'path': (
            r".",
            r"{PROGRAMFILES}\Vendor\Product",
            r"{PROGRAMFILES(X86)}\Vendor\Product",
        ),
        'header': 'ESLSCDLL.h'
    },
}

lib_names = {'win*:64': 'ESLSCDLLx64.dll'}


def build():
    build_lib(header_info, lib_names, '_eslslib', __file__)
    
build()