# -*- coding: utf-8 -*-
"""
Created on Thu Feb 28 12:08:01 2019

@author: localadmin
"""

from nicelib import load_lib, NiceLib, Sig, NiceObject, RetHandler, ret_ignore
from dataclasses import dataclass
from typing import Tuple
import numpy as np
import time


class ESLS(NiceLib):
    _info_ = load_lib('esls', __package__)    
    _prefix_ = 'DLL'

    GetProcessCount = Sig()
    GetThreadCount = Sig()
    ErrMsgBoxOn = Sig()
    ErrMsgBoxOff = Sig()
    CCDDrvInit = Sig('in')
    
    ReadRingBlock = Sig('in', 'in', 'in')
    StartFetchRingBuf = Sig()
    RingValid = Sig('in')
    StopRingReadThread = Sig()
    FetchLastRingLine = Sig('in')
    RingThreadIsOFF = Sig()
    
    class CCDDrv(NiceObject):
        _init_ = 'CCDDrvInit'
        _buflen_ = 2048*4
        CCDDrvExit = Sig('in')
        InitBoard = Sig('in', 'in', 'in', 'in',  'in', 'in', 'in', 'in', 'in')
        
        # Tigger funcs
        HighSlope = Sig('in')
        LowSlope = Sig('in')
        BothSlope = Sig('in')
        OutTrigHigh = Sig('in')
        OutTrigLow = Sig('in')
        OutTrigPulse = Sig('in', 'in')
        WaitTrigger = Sig('in', 'in', 'in', 'in')
        
        OpenShutter = Sig('in')
        CloseShutter = Sig('in')
        VOn = Sig('in')
        VOff = Sig('in')
        ReadKeyPort = Sig('in')
        ActMouse = Sig('in')
        DeactMouse = Sig('in')
        
        Cal16Bit = Sig('in', 'ignore')
        SetOvsmpl = Sig('in', 'in')
        ClrRead = Sig('in', 'in', 'in', 'in')
        ClrShCam = Sig('in', 'in')
        
        SetupVCLK = Sig('in', 'in', 'in')
        
        StartTimer = Sig('in', 'in')
        SWTrig = Sig('in')        
        StopFFTimer = Sig('in')
        FFValid = Sig('in')
        FlagXCKI = Sig('in')
        RSFifo = Sig('in')
        SetExtTrig = Sig('in')
        SetIntTrig = Sig('in')
        ReadFFCounter = Sig('in')
        DisableFifo = Sig('in')
        EnableFifo = Sig('in')
        #PickOneFifoscan = Sig('in', 'arr', 'ignore', 'in', 'len=in')
        FFOvl = Sig('in')
        
        StartRingReadThread = Sig('in', 'in', 'in', 'in')
        
        ReadRingCounter = Sig('in')
        #ReadRingLine = Sig('arr', 'in')
        
    
        #
        
        #ReadFifo = Sig('in', 'arr', 'in')
        ReadFFLoop = Sig('in', 'in',  'in', 'in', 'in', 'in', 'in', 'in',
                         'in', 'in', 'in', 'in', 'in')
    
        SetISPDA = Sig('in', 'in')
        SetISFFT = Sig('in', 'in')
    
ESLS.ErrMsgBoxOff()
drv = ESLS.CCDDrv(1)

from ..interfaces import ICam

@dataclass
class Cam(ICam):
    shots: int = 100
    lines: int = 2
    channels: int = 440
    busy: bool = False
    read_idx: int = 0
    last_read: np.ndarray = np.empty((0))
    
    def __post_init__(self):
        #drv.InitBoard(sym=0, burst = 1, pixel=2400, waits=2, flag816=1, pportadr=0,
        #              pclk=0, xckdelay=3)        
        drv.InitBoard(0, 1, 2400, 2, 1, 0, 0, 3)    
        drv.SetISPDA(0)
        drv.SetISFFT(1)
        drv.SetupVCLK(20, 7)   
        #drv.Cal16Bit()
        #drv.RSFifo()
        drv.HighSlope()
        drv.SetExtTrig()
        self.start_ring_thread()
        
    def start_ring_thread(self):
        drv.StartRingReadThread(4000, 31, 0)
        
    def stop_ring_thread(self):
        ESLS.StopRingReadThread()
        
    def read_ring(self) -> Tuple[np.ndarray]:
        arr = np.zeros((self.shots, 2, 2400), dtype=np.uint32)
        while drv.ReadRingCounter() < self.shots:        
            time.sleep(0.01)
        ESLS.ReadRingBlock(arr.view(np.uint32), 0, self.shots)
        x = arr
        x = x.view(np.uint16)
        x = x.ravel()[:x.size//2]
        x = x.reshape(self.shots, 2, 2400)
        
        a = x[:, 0, 100:-100]
        b = x[:, 1, 100:-100]
        return a, b
    
    def read_ring_downsample(self, N=10):
        a, b = self.read_ring()
        a = a.reshape(a.shape[0],-1, N).mean(-1)
        b = b.reshape(b.shape[0],-1, N).mean(-1)
        return a,b
    
    def read(self):        
       # drv.EnableFifo()
       # drv.SetExtTrig()
        arr = np.ones((self.shots, 2400, 4), dtype=np.uint16)*30000
        out = drv.ReadFFLoop(arr.view(np.uint16), 20, 1, 1, self.shots,
                             200, 0, 31, 0, 0, 1, 0)
        self.read_idx += 1
        self.last_read = out
        return arr 
    
    def read_lines(self, n_downsample=10):
        x = self.read()
        a = x[:, 0, 100:-100]
        b = x[:, 1, 100:-100]
        a = a.reshape(-1, n_downsample).mean(-1)
        b = b.reshape(-1, n_downsample).mean(-1)
        return a, b        
    
    def read_cam(self, n_downsample=5):
        a, b = self.read_ring()

        a = a.reshape(a.shape[0], -1, n_downsample).mean(-1)
        b = b.reshape(b.shape[0], -1, n_downsample).mean(-1)
        a = a- 1*a[:, 400:].mean(keepdims=True)
        b = b - 1*b[:, 400:].mean(keepdims=True)
        ext = np.empty((self.shots, 0))
        first = b[0, :].sum() > b[1, :].sum()

        chopper = np.ones(self.shots, dtype='bool')
        if first:
            chopper[::2] = False
        else:
            chopper[1::2] = False
        return a, b, chopper, ext

    def read_cam_signals(self):
        a, b = self.read_cam()
        a_mean = a.mean(0)
        a_std = a.std(0)
        b_mean = b.mean(0)
        b_std = b.std(0)
        out = (a_mean, a_std, 
                b_mean, b_std)
        if bytify:                        
            return [i.tobytes() for i in out]
        else:
            return out
    
    def set_shots(self, shots):
        self.shots = shots
        return True
        
    def get_shots(self):
        return self.shots
    
    def shutdown(self):
        ESLS.StopRingReadThread()
        drv.CCDDrvExit()

    
    
#import context
#plt.ylim(6900, 7000)
#plt.plot(a.ravel())
#plt.xlim(0, 5000)
if __name__ == '__main__':
    #import qtpy.QtGui as g
    cam = Cam()
    cam.start_ring_thread()
    cam.read_ring()

    #cam.stop_ring_thread()
    
#def bla():
    import pyqtgraph as pg
    app = pg.mkQApp()
    
    import qtpy.QtWidgets as qw
    
    import qtpy.QtCore as qtc
    
    
    win = qw.QWidget()
    lay = qw.QHBoxLayout(win)
    pl = pg.PlotWidget(parent=win)
    lay.addWidget(pl)
    
    mypl = pl.plotItem.plot([1,2,3])
    mypl1 = pl.plotItem.plot([1,2,3])
    pl2 = pg.PlotWidget(parent=win)
    lay.addWidget(pl2)
    win.setLayout(lay)
    mypl2 = pl2.plotItem.plot([1,2,3], pen="y")
    #mypl3 = pl.plotItem.plot([1,2,3], pen="r")
    timer = qtc.QTimer()
    def update():
        try:
            
            a, b = cam.read_ring_downsampled()

            #x1 = x[0][:, :].ravel(order='f')
            #x1 = x[0][:, 1::2].mean(-1)-x[0][:, 2::2].mean(-1)
            
            #x2 = x[1]
            print(a.shape)
        #x = x[:, 1200:1800]
            #a = a.mean(0
            a = a-a[:, -20:].mean(1, keepdims=1)
            #mypl.setData(bm-bm[-20:].mean())
            mypl.setData(b[0, :])
            #sig = 1000*np.log10(a[::2, :].mean(0)/a[1::2, :].mean(0))
            mypl1.setData(b[1, : ])
            #mypl2.setData(100*a.std(0)/a.mean(0))
            #mypl2.setData(x.ravel().view(np.uint16))
            #mypl2.setData(a[:, 120])
            #np.savetxt('krlamp_140.txt',x[0][:, :].mean(1))
            #mypl3.setData(x[5, :, 1])
            
            #mypl3.setData(3*x[-1][1050, :]-x[-1][250, :])
            #mypl2.setData(100*a.std(0)/bm)
            
            #timer.stop()
            #app.exit()
            
        except:
            timer.stop()
            cam.stop_ring_thread()
            #del cam
            raise
    
    
    timer.timeout.connect(update)
    timer.start(50)
    
    
    #window.
    
    win.show()
    
    app.exec_()
    drv.CCDDrvExit()


