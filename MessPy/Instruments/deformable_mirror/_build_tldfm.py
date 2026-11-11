
# _build_foo.py
from pathlib import Path

from nicelib import build_lib

header_info = {
    'win*': {
        'path': (
            str(Path(__file__).parent),
            r"{PROGRAMFILES}\Vendor\Product",
            r"{PROGRAMFILES(X86)}\Vendor\Product",
            r"C:\Users\tillsten\Documents\dmp40j-master\dmp40j-master\lib\dmp40",

        ),
        'header': 'TLDFM.h'
    },
}

lib_names = {'win*': r'C:\Users\tillsten\Documents\dmp40j-master\dmp40j-master\lib\dmp40\TLDFM_64'}

pre = """

#define __fastcall 
"""

def build():
    import sys
    build_lib(header_info, lib_names, '_tldfmlib', __file__, logbuf=sys.stdout, preamble=pre)

