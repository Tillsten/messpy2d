'''
Created on 22.07.2011

@author: cwu
'''
import ctypes as C

from . import Prototypes as prot


class pyPICommands:
    '''
    classdocs
    '''

    def __init__(self, dllname, funcprefix):
        '''
        Constructor
        '''
        self.dllname = dllname
        self.funcprefix = funcprefix
        self.dll_loaded = False
        self.__loadedfunctions = self.__FillFunctionInfoDictionary__()
        self.__loadedfunctions = {}
        self.__gcs1 = dllname.find('C843') >= 0
        self.__gcs1 |= dllname.find('C866') >= 0
        self.__gcs1 |= dllname.find('C865') >= 0
        self.__gcs1 |= dllname.find('HEX') >= 0
        self.__gcs1 |= dllname.find('Mercury') >= 0
        self.__gcs1 |= dllname.find('C848') >= 0
        self.__gcs1 |= dllname.find('C880') >= 0
        try:
            self.dllhandle = C.windll.LoadLibrary(dllname)
            self.dll_loaded = True
        except OSError:
            print('Could not load', dllname)

        self.__ID = -1

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if (self.__ID >= 0):
            self.CloseConnection()

    def __FillFunctionInfoDictionary__(self):
        InfoDict = {
            'CloseConnection': {'Prototyper': prot.Int_as_arg, },
            'ConnectRS232': {'Prototyper': prot.IntInt_as_arg_Int_as_ret},
            'EnumerateUSB': {'Prototyper': prot.CharBuffWithLenConstCharArr_as_arg_Long_as_ret},
            'ConnectUSB': {'Prototyper': prot.ConstCharArr_as_arg_Long_as_ret},
            'GcsCommandset': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'GcsGetAnswer': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'INI': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'FRF': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'FNL': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'FPL': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'REF': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'MNL': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'MPL': {'Prototyper': prot.LongConstCharArr_as_arg_BOOL_as_ret},
            'qVST': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qHLP': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qHPV': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qHPA': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qHDR': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qIDN': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qSAI': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'qSAI_ALL': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'TranslateError': {'Prototyper': prot.LongCharBuffWithLen_as_arg_BOOL_as_ret},
            'RON': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'POS': {'Prototyper': prot.LongConstCharArrDoubleArr_as_arg_BOOL_as_ret},
            'qPOS': {'Prototyper': prot.LongConstCharArrDoubleArr_as_arg_BOOL_as_ret},
            'MOV': {'Prototyper': prot.LongConstCharArrDoubleArr_as_arg_BOOL_as_ret},
            'qMOV': {'Prototyper': prot.LongConstCharArrDoubleArr_as_arg_BOOL_as_ret},
            'SVO': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'qSVO': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'IsMoving': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'IsReferencing': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'qRON': {'Prototyper': prot.LongConstCharArrLongArr_as_arg_BOOL_as_ret},
            'FED': {'Prototyper': prot.LongConstCharArrLongArrLongArr_as_arg_BOOL_as_ret},
            'SetQMCA': {'Prototyper': prot.LongInt8Int8Int16Int32},
            'GetQMCA': {'Prototyper': prot.LongInt8Int8Int16Int32Ptr},
            'SetQMC': {'Prototyper': prot.LongInt8Int8Int32},
            'GetQMC': {'Prototyper': prot.LongInt8Int8Int32Ptr},
            'OSM': {'Prototyper': prot.LongConstIntArrLongArrInt_as_arg_BOOL_as_ret},
            'qOSN': {'Prototyper': prot.LongConstIntArrLongArrInt_as_arg_BOOL_as_ret},
            'qDIA': {'Prototyper': prot.LongConstIntArrCharBuffWithLenInt_as_arg_BOOL_as_ret}
        }
        for key in InfoDict:
            InfoDict[key]['failedtoload'] = False;
        return InfoDict

    def __LoadFunc__(self, cmd):
        if (cmd in self.__loadedfunctions):
            if (self.__loadedfunctions[cmd]['failedtoload']):
                return None
        try:
            func = eval('self.dllhandle.' + self.funcprefix + cmd)
            if (cmd in self.__loadedfunctions):
                self.__loadedfunctions[cmd]['Prototyper'](func)
            self.__loadedfunctions[cmd] = func
        except OSError:
            print('failed to load', cmd)
            self.__loadedfunctions[cmd]['failedtoload'] = True

        return func

    def __GetFunc__(self, cmd):
        if (cmd in self.__loadedfunctions):
            return self.__loadedfunctions[cmd]
        return self.__LoadFunc__(cmd)

    def __QueryString__(self, cmd, bufsize=300):
        if (self.__ID >= 0):
            return self.__QueryStringOnInt__(cmd, self.__ID, bufsize)
        print(cmd, 'failed: no connection')
        return None

    def __QueryStringOnInt__(self, cmd, ID, bufsize=300):
        RetString = C.create_string_buffer(b"", bufsize)
        if (self.__GetFunc__(cmd)(ID, RetString, bufsize - 1) == 0):
            raise Exception(cmd + ' failed. bufsize:' + str(bufsize))
        return RetString.value

    def __create_axes_list__(self, axes):
        if (self.__gcs1):
            return [axis for axis in axes.replace(' ', '')]
        axes = axes.replace('\n', '')
        return axes.strip().split(' ')

    def __create_axes_buffer__(self, axes_list):
        if (self.__gcs1):
            return C.create_string_buffer(''.join(axes_list))
        return C.create_string_buffer((''.join(axes_list)).encode())

    def ____create_axes_buffer___str__(self, axes_str):
        if (type(axes_str) == 'str'):
            axeslist = self.__create_axes_list__(axes_str)
        else:
            axeslist = axes_str
        return self.__create_axes_buffer__(axeslist)

    def __SetDoublesOfAxes__(self, cmd, axesvaluesdict):
        if (self.__ID >= 0):
            axis_buff = self.__create_axes_buffer__([str(i) for i in axesvaluesdict])
            inBuff = (C.c_double * len(axesvaluesdict))()
            inBuff[:] = list(map(axesvaluesdict.get, list(axesvaluesdict.keys())))
            return self.__GetFunc__(cmd)(self.__ID, axis_buff, inBuff)

    def __QueryDoublesOfAxes__(self, cmd, axes):
        if (self.__ID >= 0):
            axes_list = self.__create_axes_list__(axes)
            axes_buff = self.__create_axes_buffer__(axes_list)
            outBuff = (C.c_double * len(axes_list))()
            self.__GetFunc__(cmd)(self.__ID, axes_buff, outBuff)
            return dict(list(zip(axes_list, outBuff)))

    def __SetIntOfAxes__(self, cmd, axesvaluesdict):
        if (self.__ID >= 0):
            inBuff = (C.c_int * len(axesvaluesdict))()
            inBuff[:] = list(map(axesvaluesdict.get, list(axesvaluesdict.keys())))

            axis_buff = self.__create_axes_buffer__(list(axesvaluesdict.keys()))
            return self.__GetFunc__(cmd)(self.__ID, axis_buff, inBuff)

    def __SetIntOfChannels__(self, cmd, channelsvaluesdict):
        if (self.__ID >= 0):
            nrItems = len(channelsvaluesdict)
            inBuff = (C.c_int * nrItems)()
            inBuff[:] = list(map(channelsvaluesdict.get, list(channelsvaluesdict.keys())))
            channelBuff = (C.c_int * nrItems)()
            channelBuff[:] = list(channelsvaluesdict.keys())

            return self.__GetFunc__(cmd)(self.__ID, channelBuff, inBuff, nrItems)

    def __GetIntOfChannels__(self, cmd, channels):
        if (self.__ID >= 0):
            nrItems = len(channels)
            inBuff = (C.c_int * nrItems)()
            channelBuff = (C.c_int * nrItems)()
            channelBuff[:] = channels

            bOK = self.__GetFunc__(cmd)(self.__ID, channelBuff, inBuff, nrItems)
            if (bOK == False):
                return None
            return dict(list(zip(channels, inBuff)))

    def __GetIntOfAxes__(self, cmd, axes):
        if (self.__ID >= 0):
            axes_list = self.__create_axes_list__(axes)
            axes_buff = self.__create_axes_buffer__(axes_list)
            inBuff = (C.c_int * len(axes_buff))()

            bOK = self.__GetFunc__(cmd)(self.__ID, axes_buff, inBuff)
            if (bOK == False):
                return None
            return dict(list(zip(axes_list, inBuff)))

    def __DoCommandOnAxes__(self, cmd, axes):
        if (self.__ID >= 0):
            axes_buff = self.____create_axes_buffer___str__(axes)
            return self.__GetFunc__(cmd)(self.__ID, axes_buff)

    def CloseConnection(self):
        if (self.__ID >= 0):
            self.__GetFunc__('CloseConnection')(self.__ID)

    def ConnectRS232(self, com, baud):
        if not (self.dll_loaded):
            print('Cannot connect, no DLL loaded')
            return False
        else:
            self.__ID = self.__GetFunc__('ConnectRS232')(com, baud)
            return self.__ID > -1

    def Connect(self, devnr):
        if not (self.dll_loaded):
            print('Cannot connect, no DLL loaded')
            return False
        else:
            self.__ID = self.__GetFunc__('Connect')(devnr)
            return self.__ID > -1

    def ConnectTCPIP(self, host, port):
        if not (self.dll_loaded):
            print('Cannot connect, no DLL loaded')
            return False
        else:
            hostbuf = C.create_string_buffer(host)
            self.__ID = self.__GetFunc__('ConnectTCPIP')(hostbuf, port)
            return self.__ID > -1

    def EnumerateUSB(self, filter=''):
        if not (self.dll_loaded):
            print('Cannot connect, no DLL loaded')
            return None
        else:
            filterbuf = C.create_string_buffer(filter)
            listbuf = C.create_string_buffer(1000)
            self.__GetFunc__('EnumerateUSB')(listbuf, 999, filterbuf)
            Devices = listbuf.value.splitlines()
            return Devices

    def ConnectUSB(self, devicename):
        if not (self.dll_loaded):
            print('Cannot connect, no DLL loaded')
            return False
        else:
            devicenamebuf = C.create_string_buffer(devicename)
            self.__ID = self.__GetFunc__('ConnectUSB')(devicenamebuf)
            return self.__ID > -1

    def qIDN(self):
        return self.__QueryString__('qIDN')

    def qHDR(self):
        return self.__QueryString__('qHDR', 10000)

    def qHPA(self):
        return self.__QueryString__('qHPA', 10000)

    def qHLP(self):
        return self.__QueryString__('qHLP', 10000)

    def GcsGetAnswer(self):
        return self.__QueryString__('GcsGetAnswer', 10000)

    def qSAI(self):
        return self.__QueryString__('qSAI', 100)

    def qSAI_ALL(self):
        return self.__QueryString__('qSAI_ALL', 100)

    def TranslateError(self, errorid):
        return self.__QueryStringOnInt__('TranslateError', errorid)

    #    def qSAI(self):
    #        if(self.__ID >= 0):
    #            SAIString = C.create_string_buffer("",32)
    #            self.__GetFunc__('qSAI')(self.__ID,SAIString,31)
    #            return SAIString.value
    #        return None

    def CST(self, axisstagedict):
        if (self.__ID >= 0):
            axis_buff = self.__create_axes_buffer__(list(axisstagedict.keys()))
            stage_buff = C.create_string_buffer('\n'.join(map(axisstagedict.get, list(axisstagedict.keys()))))
            return self.__GetFunc__('CST')(self.__ID, axis_buff, stage_buff)
        return None

    def qCST(self, axis=''):
        if (self.__ID >= 0):
            axis_buff = self.____create_axes_buffer___str__(axis)
            stage_buff = C.create_string_buffer("", 256)
            if (self.__GetFunc__('qCST')(self.__ID, axis_buff, stage_buff, 255)):
                answer = stage_buff.value.splitlines()
                lin2 = [line.strip() for line in answer]
                return dict([line.split('=') for line in lin2])
        return None

    def qERR(self):
        if (self.__ID >= 0):
            val = C.c_int()
            self.__GetFunc__('qERR')(self.__ID, C.byref(val))
            return val.value

    def FNL(self, axis=''):
        return self.__DoCommandOnAxes__('FNL', axis)

    def FRF(self, axis=''):
        return self.__DoCommandOnAxes__('FRF', axis)

    def FPL(self, axis=''):
        return self.__DoCommandOnAxes__('FPL', axis)

    def MNL(self, axis=''):
        return self.__DoCommandOnAxes__('MNL', axis)

    def REF(self, axis=''):
        return self.__DoCommandOnAxes__('REF', axis)

    def MPL(self, axis=''):
        return self.__DoCommandOnAxes__('MPL', axis)

    def IsMoving(self, axes=''):
        return self.__GetIntOfAxes__('IsMoving', axes)

    def IsReferencing(self, axes=''):
        return self.__GetIntOfAxes__('IsReferencing', axes)

    def SetQMCA(self, cmd, axis, param1, param2):
        if (self.__ID >= 0):
            return self.__GetFunc__('SetQMCA')(self.__ID, cmd, axis, param1, param2)

    def GetQMCA(self, cmd, axis, param1):
        if (self.__ID >= 0):
            val = C.c_int32()
            OK = self.__GetFunc__('GetQMCA')(self.__ID, cmd, axis, param1, C.byref(val))
            return val.value

    def SetQMC(self, cmd, axis, param):
        if (self.__ID >= 0):
            return self.__GetFunc__('SetQMC')(self.__ID, cmd, axis, param)

    def GetQMC(self, cmd, axis, param):
        if (self.__ID >= 0):
            val = C.c_int32()
            OK = self.__GetFunc__('GetQMC')(self.__ID, cmd, axis, C.byref(val))
            return val.value

    def GcsCommandset(self, command):
        if (self.__ID >= 0):
            cmd_buff = C.create_string_buffer(command)
            return self.__GetFunc__('GcsCommandset')(self.__ID, cmd_buff)

    def RTR(self, value):
        if (self.__ID >= 0):
            return self.__GetFunc__('RTR')(self.__ID, value)

    def qDRR_SYNC(self, TableID, Start, Number):
        if (self.__ID >= 0):
            inBuff = (C.c_double * Number)()
            bOK = self.__GetFunc__('qDRR_SYNC')(self.__ID, TableID, Start, Number, inBuff)
            if (bOK != 1):
                raise Exception('qDRR_SYNC(' + str(self.__ID) + ',' + str(TableID) + ',' + str(Start) + ',' + str(
                    Number) + ') failed')
            return list(inBuff)

    def POS(self, axesvaluesdict):
        return self.__SetDoublesOfAxes__('POS', axesvaluesdict)

    def qPOS(self, axes):
        return self.__QueryDoublesOfAxes__('qPOS', axes)

    def MOV(self, axesvaluesdict):
        return self.__SetDoublesOfAxes__('MOV', axesvaluesdict)

    def qMOV(self, axes=''):
        return self.__QueryDoublesOfAxes__('qMOV', axes)

    def MVR(self, axesvaluesdict):
        return self.__SetDoublesOfAxes__('MVR', axesvaluesdict)

    def VEL(self, axesvaluesdict):
        return self.__SetDoublesOfAxes__('VEL', axesvaluesdict)

    def qVEL(self, axes=''):
        return self.__QueryDoublesOfAxes__('qVEL', axes)

    def qTMN(self, axes=''):
        return self.__QueryDoublesOfAxes__('qTMN', axes)

    def qTMX(self, axes=''):
        return self.__QueryDoublesOfAxes__('qTMX', axes)

    def qFRF(self, axes=''):
        return self.__GetIntOfAxes__('qFRF', axes)

    def RON(self, axesvaluesdict):
        return self.__SetIntOfAxes__('RON', axesvaluesdict)

    def OSM(self, channelvaluesdict):
        return self.__SetIntOfChannels__('OSM', channelvaluesdict)

    def qOSN(self, channels):
        return self.__GetIntOfChannels__('qOSN', channels)

    def SVO(self, axesvaluesdict):
        return self.__SetIntOfAxes__('SVO', axesvaluesdict)

    def qSVO(self, axes=''):
        return self.__GetIntOfAxes__('qSVO', axes)

    def qRON(self, axes=''):
        return self.__GetIntOfAxes__('qRON', axes)

    def qTSP(self, axis=''):
        if (self.__ID >= 0):
            val = C.c_double(0)
            channelId = C.c_int(int(axis))
            self.__GetFunc__('qTSP')(self.__ID, C.byref(channelId), C.byref(val), 1)
            return val.value

    def GetError(self):
        return self.__GetFunc__('GetError')(self.__ID)

    def qVST(self):
        qVSTString = self.__QueryString__('qVST', 10000)
        retlist = qVSTString.splitlines()
        return [line.strip() for line in retlist]

    def INI(self, axes=''):
        return self.__DoCommandOnAxes__('INI', axes)

    def WAV_SIN_P(self, WaveTableId, OffsetOfFirstPointInWaveTable, NumberOfPoints, AddAppendWave, CenterPointOfWave,
                  AmplitudeOfWave, OffsetOfWave, SegmentLength):
        if (self.__ID >= 0):
            return self.__GetFunc__('WAV_SIN_P')(self.__ID, C.c_int(WaveTableId),
                                                 C.c_int(OffsetOfFirstPointInWaveTable), C.c_int(NumberOfPoints),
                                                 C.c_int(AddAppendWave), C.c_int(CenterPointOfWave),
                                                 C.c_double(AmplitudeOfWave), C.c_double(OffsetOfWave),
                                                 C.c_int(SegmentLength))

    def WAV_RAMP(self, WaveTableId, OffsetOfFirstPointInWaveTable, NumberOfPoints, AddAppendWave, CenterPointOfWave,
                 NumberOfSpeedUpDownPointsInWave, AmplitudeOfWave, OffsetOfWave, SegmentLength):
        if (self.__ID >= 0):
            return self.__GetFunc__('WAV_RAMP')(self.__ID, C.c_int(WaveTableId), C.c_int(OffsetOfFirstPointInWaveTable),
                                                C.c_int(NumberOfPoints), C.c_int(AddAppendWave),
                                                C.c_int(CenterPointOfWave), C.c_int(NumberOfSpeedUpDownPointsInWave),
                                                C.c_double(AmplitudeOfWave), C.c_double(OffsetOfWave),
                                                C.c_int(SegmentLength))

    def WAV_LIN(self, WaveTableId, OffsetOfFirstPointInWaveTable, NumberOfPoints, AddAppendWave,
                NumberOfSpeedUpDownPointsInWave, AmplitudeOfWave, OffsetOfWave, SegmentLength):
        if (self.__ID >= 0):
            return self.__GetFunc__('WAV_LIN')(self.__ID, C.c_int(WaveTableId), C.c_int(OffsetOfFirstPointInWaveTable),
                                               C.c_int(NumberOfPoints), C.c_int(AddAppendWave),
                                               C.c_int(NumberOfSpeedUpDownPointsInWave), C.c_double(AmplitudeOfWave),
                                               C.c_double(OffsetOfWave), C.c_int(SegmentLength))

    def WAV_PNT(self, WaveTableId, OffsetOfFirstPointInWaveTable, NumberOfPoints, AddAppendWave, WavePoints):
        if (self.__ID >= 0):
            inBuff = (C.c_double * len(WavePoints))()
            i = 0
            for value in WavePoints:
                inBuff[i] = value
                i = i + 1

            return self.__GetFunc__('WAV_PNT')(self.__ID, C.c_int(WaveTableId), C.c_int(OffsetOfFirstPointInWaveTable),
                                               C.c_int(NumberOfPoints), C.c_int(AddAppendWave), inBuff)

    def qWAV(self, WaveTableId_ParameterId_Tuple_List):
        if (self.__ID >= 0):
            outValuesBuff = (C.c_double * len(WaveTableId_ParameterId_Tuple_List))()
            inWaveTablBuff = (C.c_int * len(WaveTableId_ParameterId_Tuple_List))()
            inParameterBuff = (C.c_int * len(WaveTableId_ParameterId_Tuple_List))()
            inWaveTablBuff[:] = [x[0] for x in WaveTableId_ParameterId_Tuple_List]
            inParameterBuff[:] = [x[1] for x in WaveTableId_ParameterId_Tuple_List]
            self.__GetFunc__('qWAV')(self.__ID, inWaveTablBuff, inParameterBuff, outValuesBuff,
                                     len(WaveTableId_ParameterId_Tuple_List))
            return dict(list(zip(list(zip(inWaveTablBuff, inParameterBuff)), outValuesBuff)))

    def DRC(self, RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List):
        if (self.__ID >= 0):
            inRecordTableBuff = (C.c_int * len(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List))()
            inRecordOptionBuff = (C.c_int * len(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List))()
            inRecordTableBuff[:] = list(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List.keys())
            inRecordOptionBuff[:] = [x[1] for x in
                                     map(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List.get,
                                         list(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List.keys()))]
            inRecordSourceBuff = self.__create_axes_buffer__([x[0] for x in map(
                RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List.get,
                list(RecordTableId_RecordSourceId_RecordOption_Tuple_Dictonary_List.keys()))])
            return self.__GetFunc__('DRC')(self.__ID, inRecordTableBuff, inRecordSourceBuff, inRecordOptionBuff)

    def qDRC(self, RecordTableId_RecordSourceId_List):
        if (self.__ID >= 0):
            inRecordTableBuff = (C.c_int * len(RecordTableId_RecordSourceId_List))()
            outRecordOptionBuff = (C.c_int * len(RecordTableId_RecordSourceId_List))()
            inRecordTableBuff[:] = RecordTableId_RecordSourceId_List[:]
            outRecordSourceBuff = C.create_string_buffer("", 1024)
            self.__GetFunc__('qDRC')(self.__ID, inRecordTableBuff, outRecordSourceBuff, outRecordOptionBuff, 1024,
                                     len(RecordTableId_RecordSourceId_List))
            tmpRecordSourceBuff = self.__create_axes_list__(C.string_at(outRecordSourceBuff))
            return dict(list(zip(inRecordTableBuff, list(zip(tmpRecordSourceBuff, outRecordOptionBuff)))))

    def WSL(self, WaveGeneratorId_WaveTableId_Dictonary):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_WaveTableId_Dictonary))()
            inWaveTableBuff = (C.c_int * len(WaveGeneratorId_WaveTableId_Dictonary))()
            inWaveGeneratorBuff[:] = list(WaveGeneratorId_WaveTableId_Dictonary.keys())
            inWaveTableBuff[:] = list(
                map(WaveGeneratorId_WaveTableId_Dictonary.get, list(WaveGeneratorId_WaveTableId_Dictonary.keys())))
            return self.__GetFunc__('WSL')(self.__ID, inWaveGeneratorBuff, inWaveTableBuff,
                                           len(WaveGeneratorId_WaveTableId_Dictonary))

    def qWSL(self, WaveGeneratorId_List):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_List))()
            inWaveTableBuff = (C.c_int * len(WaveGeneratorId_List))()
            inWaveGeneratorBuff[:] = WaveGeneratorId_List[:]
            self.__GetFunc__('qWSL')(self.__ID, inWaveGeneratorBuff, inWaveTableBuff, len(WaveGeneratorId_List))
            return dict(list(zip(inWaveGeneratorBuff, inWaveTableBuff)))

    def CTO(self, TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List):
        if (self.__ID >= 0):
            inTriggrtOutputBuff = (C.c_int * len(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List))()
            inTriggerParameterBuff = (C.c_int * len(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List))()
            inValueBuff = (C.c_double * len(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List))()
            inTriggrtOutputBuff[:] = [x[0] for x in
                                      list(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List.keys())]
            inTriggerParameterBuff[:] = [x[1] for x in
                                         list(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List.keys())]
            inValueBuff[:] = list(map(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List.get,
                                      list(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List.keys())))
            return self.__GetFunc__('CTO')(self.__ID, inTriggrtOutputBuff, inTriggerParameterBuff, inValueBuff,
                                           len(TriggrtOutputId_TriggerParameterId_Vallue_Dictonary_Tuple_List))

    def qCTO(self, TriggrtOutputId_TriggerParameterId_Tuple_List):
        if (self.__ID >= 0):
            inTriggrtOutputBuff = (C.c_int * len(TriggrtOutputId_TriggerParameterId_Tuple_List))()
            inTriggerParameterBuff = (C.c_int * len(TriggrtOutputId_TriggerParameterId_Tuple_List))()
            outValueBuff = (C.c_double * len(TriggrtOutputId_TriggerParameterId_Tuple_List))()
            inTriggrtOutputBuff[:] = [x[0] for x in TriggrtOutputId_TriggerParameterId_Tuple_List]
            inTriggerParameterBuff[:] = [x[1] for x in TriggrtOutputId_TriggerParameterId_Tuple_List]
            self.__GetFunc__('qCTO')(self.__ID, inTriggrtOutputBuff, inTriggerParameterBuff, outValueBuff,
                                     len(TriggrtOutputId_TriggerParameterId_Tuple_List))
            return dict(list(zip(list(zip(inTriggrtOutputBuff, inTriggerParameterBuff)), outValueBuff)))

    def WGC(self, WaveGeneratorId_NumberOfCycles_Dictonary):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_NumberOfCycles_Dictonary))()
            inNumberOfCyclesBuff = (C.c_int * len(WaveGeneratorId_NumberOfCycles_Dictonary))()
            inWaveGeneratorBuff[:] = list(WaveGeneratorId_NumberOfCycles_Dictonary.keys())
            inNumberOfCyclesBuff[:] = list(map(WaveGeneratorId_NumberOfCycles_Dictonary.get,
                                               list(WaveGeneratorId_NumberOfCycles_Dictonary.keys())))
            return self.__GetFunc__('WGC')(self.__ID, inWaveGeneratorBuff, inNumberOfCyclesBuff,
                                           len(WaveGeneratorId_NumberOfCycles_Dictonary))

    def qWGC(self, WaveGeneratorId_List):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_List))()
            outNumberOfCyclesBuff = (C.c_int * len(WaveGeneratorId_List))()
            inWaveGeneratorBuff[:] = WaveGeneratorId_List[:]
            self.__GetFunc__('qWGC')(self.__ID, inWaveGeneratorBuff, outNumberOfCyclesBuff, len(WaveGeneratorId_List))
            return dict(list(zip(inWaveGeneratorBuff, outNumberOfCyclesBuff)))

    def WGO(self, WaveGeneratorId_StartMode_Dictonary):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_StartMode_Dictonary))()
            inStartModeBuff = (C.c_int * len(WaveGeneratorId_StartMode_Dictonary))()
            inWaveGeneratorBuff[:] = list(WaveGeneratorId_StartMode_Dictonary.keys())
            inStartModeBuff[:] = list(
                map(WaveGeneratorId_StartMode_Dictonary.get, list(WaveGeneratorId_StartMode_Dictonary.keys())))
            return self.__GetFunc__('WGO')(self.__ID, inWaveGeneratorBuff, inStartModeBuff,
                                           len(WaveGeneratorId_StartMode_Dictonary))

    def qDIA(self, items):
        nrItems = len(items)
        itemBuff = (C.c_int * nrItems)()
        itemBuff[:] = items
        bufsize = nrItems * 100
        RetString = C.create_string_buffer("", bufsize)
        if (self.__GetFunc__('qDIA')(self.__ID, itemBuff, RetString, bufsize - 1, nrItems) == 0):
            raise Exception('qDIA failed. bufsize:' + str(bufsize))
        return RetString.value

    def qWGO(self, WaveGeneratorId_List):
        if (self.__ID >= 0):
            inWaveGeneratorBuff = (C.c_int * len(WaveGeneratorId_List))()
            outStartModeBuff = (C.c_int * len(WaveGeneratorId_List))()
            inWaveGeneratorBuff[:] = WaveGeneratorId_List[:]
            self.__GetFunc__('qWGO')(self.__ID, inWaveGeneratorBuff, outStartModeBuff, len(WaveGeneratorId_List))
            return dict(list(zip(inWaveGeneratorBuff, outStartModeBuff)))


import subprocess


def test_me():
    # servr = testserver('localhost',5000)

    child = subprocess.Popen("c:\\python27\\python.exe d:\\Code\\PythonSchulung\\Freitag\\src\\server2.py", shell=True)
    # os.startfile('c:\\python27\\python.exe d:\\Code\\PythonSchulung\\Freitag\\src\\server2.py')
    # cmd = pyPICommands('PI_Mercury_GCS_DLL','Mercury_')
    cmd = pyPICommands('PI_GCS2_DLL', 'PI_')
    # cmd = pyPICommands('C843_GCS_DLL','C843_')
    # if not cmd.ConnectRS232(1, 115200):
    if not cmd.ConnectTCPIP('localhost', 5000):
        print('could not connect')
        return

    print('connected to ', cmd.qIDN())
    # print 'GetError returned', cmd.GetError()
    print('POS?: ', cmd.qPOS(''))
    return
    axes = cmd.qSAI()
    print('available axes:', axes)
    connectedstages = cmd.qCST(axes)
    print('connected:', connectedstages)
    print('svo =', cmd.qSVO(axes))

    print('err:', cmd.qERR())
    # frf = cmd.qFRF(axes)


def test_USB():
    cmd = pyPICommands('PI_GCS2_DLL', 'PI_')
    AvailableUSBDevices = cmd.EnumerateUSB('')
    if (len(AvailableUSBDevices) > 0):
        print('try to connect with', AvailableUSBDevices[0])
        cmd.ConnectUSB(AvailableUSBDevices[0])
        print('connected to ', cmd.qIDN())
    cmd2 = pyPICommands('PI_GCS2_DLL', 'PI_')
    AvailableUSBDevices = cmd2.EnumerateUSB('')
    if (len(AvailableUSBDevices) > 0):
        print('try to connect with', AvailableUSBDevices[0])
        cmd2.ConnectUSB(AvailableUSBDevices[0])
        print('connected to ', cmd2.qIDN())
    cmd.CloseConnection()
    cmd2.CloseConnection()


def testaxeslists():
    cmd = pyPICommands('C843_GCS_DLL', 'C843_')
    assert cmd.gcs1 == True
    assert cmd.__create_axes_list__('A BC') == ['A', 'B', 'C']
    assert cmd.__create_axes_buffer__(cmd.__create_axes_list__(' A B C ')).value == 'ABC'
    assert cmd.__create_axes_buffer__(cmd.__create_axes_list__('ABC')).value == 'ABC'

    cmd2 = pyPICommands('PI_GCS2_DLL', 'PI_')
    assert cmd2.gcs1 == False
    assert cmd2.__create_axes_list__('A BC') == ['A', 'BC']
    assert cmd2.__create_axes_list__('ABC') == ['ABC']
    # stripping:
    assert cmd2.__create_axes_buffer__(cmd2.__create_axes_list__(' A B C ')).value == 'A B C'
    print('testaxeslists complete.')


def testmultiaxisGCS1():
    cmd = pyPICommands('C843_GCS_DLL', 'C843_')
    assert cmd.gcs1 == True
    cmd.Connect(2)
    # print cmd.qVST()
    # dicts are not sorted!
    assert cmd.qCST('1234') == {'1': 'NOSTAGE', '3': 'NOSTAGE', '2': 'NOSTAGE', '4': 'NOSTAGE'}
    assert cmd.qCST('12') == {'1': 'NOSTAGE', '2': 'NOSTAGE'}
    assert cmd.qCST('123') == {'1': 'NOSTAGE', '2': 'NOSTAGE', '3': 'NOSTAGE'}
    assert cmd.qCST('133') == {'1': 'NOSTAGE', '3': 'NOSTAGE'}
    cmd.CST({'1': 'C-136.10', '3': 'C-150.PD'})
    assert cmd.qCST('13') == {'1': 'C-136.10', '3': 'C-150.PD'}
    assert cmd.qCST('') == {'1': 'C-136.10', '3': 'C-150.PD', '2': 'NOSTAGE', '4': 'NOSTAGE'}
    print('cst test complete')
    cmd.INI('13')
    cmd.SVO({'1': 1, '3': 0})
    assert cmd.qSVO('13') == {'1': 1, '3': 0}
    cmd.SVO({'1': 0, '3': 1})
    assert cmd.qSVO('13') == {'1': 0, '3': 1}
    cmd.SVO({'1': 0, '3': 0})
    assert cmd.qSVO('13') == {'1': 0, '3': 0}
    cmd.POS({'1': 0.5, '3': 1.3})
    assert cmd.qPOS('13') == {'1': 0.49794252394835486, '3': 1.26}
    print('INI , RON, POS POS? complete')


if __name__ == '__main__':  # 5
    test_USB()
    testaxeslists()
    testmultiaxisGCS1()
    # testme()
