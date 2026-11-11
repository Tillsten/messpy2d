import logging

import cppyy

logger = logging.Logger("C843")
cppyy.add_include_path(r"C:\Users\Public\PI\C-843\PI_Programming_Files_C843_GCS_DLL")
cppyy.add_library_path(r"C:\Users\Public\PI\C-843\PI_Programming_Files_C843_GCS_DLL")

cppyy.include('C843_GCS_DLL.h')
cppyy.load_library('C843_GCS_DLL_x64.dll')

from ctypes import *

g = cppyy.gbl
dbl = (c_double*1)
c_bool = (c_int * 1)

class C843:
    def __init__(self, lastpos=None):
        logger.info("Connecting C843-Board")
        self.bidx = g.C843_Connect(1)
        g.C843_CST(self.bidx, '2', "M-414.1PD")
        g.C843_INI(self.bidx, '2')

        logger.info("Referencing")
        if lastpos is None:
            b = c_bool()
            g.C843_qFRF(self.bidx, '2', b)
            print('qRef', b[0])
            print(g.C843_FRF(self.bidx, '2'))
            while True:
                g.C843_IsReferencing(self.bidx, '2', b)
                if not b[0]:
                    break
        g.C843_ACC(self.bidx, '2', dbl(500))
        g.C843_DEC(self.bidx, '2', dbl(500))

    def move_mm(self, pos):
        pos = dbl(pos)
        g.C843_MOV(self.bidx, '2', pos)

    def get_pos_mm(self):
        pos = dbl()
        g.C843_qPOS(self.bidx, '2', pos)
        return pos[0]

    def is_moving(self):
        mov = c_bool()
        g.C843_IsMoving(self.bidx, '2', mov)
        return mov[0]

if __name__ == '__main__':
    c843 = C843()
    c843.move_mm(20.)
    while c843.is_moving():
        print(c843.get_pos_mm())