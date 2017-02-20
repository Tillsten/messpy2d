# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 17:40:25 2013

@author: tillsten
"""

from __future__ import print_function
import serial
import time
import numpy as np

DEBUG = True

class TriaxSpectrometer(object):
    step_slit = 2

    def __init__(self, com_port='COM2'):
        port = serial.Serial(com_port, 9600, xonxoff=True)
        port.flush()
        self.disp = None
        self.wl = 500
        self.port = port
        self.lines_grating = 100.
        self.write(" ")
        port.timeout = 10
        out = port.read(1)
        print(out)
        if len(out) == 0:
            print("Can't connect to Triax Spectrometer")
            raise IOError

        if out=='B':

            self.write('O2000'+chr(0))
            out = port.read(1)
            if len(out) == 0 or out=='F':
                print("Can't connect to Triax Spectrometer")
                raise IOError

            self.write(" ")

            out = port.read(1)
            if len(out) == 0 or out=='F':
                print("Can't connect to Triax Spectrometer")
                raise IOError

            self.write("A")

            out = port.read(1)
            if out!='o':
                print("Init of Triax Spectrometer failed")
                raise IOError


            self.write("i,0,0,0\r")
            out = port.read(1)
            if out!='o':
                print("Init of Triax Spectrometer failed")
                raise IOError

        #self.motor_init()
        self.get_wl()
        self.get_slit()

    def write(self, bstring):
        self.port.flush()
        if DEBUG:
            print('WRITE "%s"'%str(bstring))
        self.port.write(bstring)

    def read(self, ):
        pass

    def motor_init(self):

        self.port.timeout = 20
        self.write("A")
        print(self.port.read(1))

    def set_wl(self, wl):
        port = self.port
        wl = wl / 1200. * self.lines_grating
        self.write("Z61,1,"+str(round(wl,2))+"\r")
        if port.read(1)!="o":
            print("Setting wl failed")
            raise IOError

        out = "q"
        while out=="q":
            self.write("E")
            out = port.read(1)
            out = port.read(1)
            print(out)
            time.sleep(0.1)
        self.get_wl()

    def get_wl(self):
        port = self.port
        self.write("Z62,1\r")
        out = port.read(1)
        print(out)
        if out == "b":
            out = port.read(1)
        if out == "F":
            out = port.read(1)
        if out == "o":
            o = readline(port)
            print(o)
            read_wl = float(o[:-1])
            wl = read_wl * 1200 / self.lines_grating
            self.wl_pos = wl
            return wl
        else:
            print(out,  port.read(1))
           
            print("Getting wl failed")
            raise IOError

    def read_until(self, terminator='\r'):
        l = []
        while True:
            r = self.port.read(1)
            print("r ", r)
            if r == terminator:
                break
            l.append(r)
        return "".join(l)

    def get_slit(self):
        "Get slit setting in micrometer."
        port = self.port
        self.write("j0,0\r")

        out = port.read(1)
        print(out)
        if out != "o":
            print("Getting slitpos failed")
            raise IOError
        else:
            out = self.read_until()
            print('readallslit', out)
            read_slit = float(out)
            self.slit_pos =  int(read_slit) * 2
            print(self .slit_pos)
            return int(read_slit) * 2

    def set_slit(self, slit_width):
        port = self.port
        cur_slit_width = self.get_slit()
        change = int((slit_width - cur_slit_width) /2)
        self.write("k0,0," + str(change) + "\r")
        if port.read(1)!="o":
            print("Setting slit failed")
            raise IOError

        out = 'q'
        while out=="q":
            self.write("E")
            out = port.read(1)
            out = port.read(1)
            print(out)
            time.sleep(0.04)


    def calc_wavelengths(self, wl, grating=150.):
        if self.disp is not None:
            x = np.arange(16)-8
            return x*self.disp + wl
            
        WaveZero = 7
        Wavecorrection = 0
        Gamma = 15 / 180. * 3.1415
        f = 193.  #193
        spacing = 0.6  #0.6
        d = 1 / self.lines_grating * 1000000#
        cwl = wl
        Dispersion = spacing * (np.sqrt(d * d * np.cos(Gamma)**2 - cwl**2  / 4.) - np.tan(Gamma) * cwl / 2.) / f
        Dispersion = -Dispersion / cwl**2 * 10000000.
        chan = np.arange(1, 17)
        try:
            WavelengthChannel = 1 / cwl * 10000000. + (-chan + WaveZero) * Dispersion + Wavecorrection
        except ZeroDivisionError:
            return np.arange(16)-8
        return 1e7/WavelengthChannel


def readline(port, eol='\r'):
    out = list(port.read(1))
    while out[-1] != eol:
        out.append(port.read(1))
    return "".join(out)


spec = TriaxSpectrometer('COM2')

print(spec.set_slit(50))
#print(spec.get_slit())








                #