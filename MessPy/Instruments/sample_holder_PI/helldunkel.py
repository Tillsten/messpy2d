import serial

DEBUG = True
CRLF = '\r\n'.encode('ascii')

COMMAND_LIST = [
    ('counter_value', 0, (0, 65535)),
    ('pd1_offset', 1, (0, 4095)),
    ('pd2_offset', 2, (0, 4095)),
    ('dac_flag', 3, (0, 1)),
    ('rs232_mode', 4, (0, 2)),
    ('target_counts', 5, (0, 4095)),
    ('output_mode', 6, (0, 1)),
    ('test_mode', 9, (0, 1)),
    ('pd_signal', 20, (0, 2)),
    ('pd1_polarity', 21, (0, 2)),
    ('pd2_polarity', 22, (0, 2)),
    ('pd1_score_list', 10, None, 'G', 'ASCII'),
    ('compilation_stamp', 99, None, 'G', 'ASCII'),
    ('counter_table', 12, None, 'G', True),
    ('start_offset_calc', 0, None, 'T'),
    ('stop_offset_calc', 1, None, 'T'),
]


class FringeCounter:
    '''
    FringeCounter, controling the HellDunkelZaehler from Hamm Group.
    '''
    def __init__(self, com_port="COM3"):
        for c in COMMAND_LIST:
            self.make_command(*c)
        self.port = serial.Serial(port=com_port, baudrate=115200)

    def send_cmd(self, cmd):
        '''
        Encodes cmd to ASCII, adds lineterminator, writes cmd to port
        and check the answer. If successful, return the answer.
        '''
        cmd = cmd.encode('ASCII') + CRLF
        if DEBUG:
            print('SEND: ', cmd)
        expected_answ = cmd[0:1].lower() + cmd[1:5]
        self.port.write(cmd)
        answ = self.port.read_until(terminator=CRLF)
        if DEBUG:
            print('ANSW: ', answ)
        if answ[0] == expected_answ[0]:
            return answ[:-2]
        else:
            raise OSError(f'Send: {cmd}, Answ: {answ}')

    def make_command(self,
                     name,
                     addr,
                     value_range=None,
                     mode='SG',
                     extra_output=False):
        'helper method to generate setter and getter functions'
        
        if 'S' in mode:
            def setter(value):
                if value_range is not None:
                    if not value_range[0] <= value <= value_range[1]:
                        err_msg = 'Value of {} outside allowed range of {}-{}'
                        raise ValueError(err_msg.format(value, *value_range))

                cmd = f'S {addr: 02d} {value: d}'
                self.send_cmd(cmd)            
            setattr(self, "set_" + name, setter)

        if 'G' in mode:
            def getter():
                cmd = f'G {addr: 02d} 0'
                ans = self.send_cmd(cmd)
                if extra_output == 'ASCII':
                    n = int(ans.split(b' ')[1])
                    ans = [ans]
                    for i in range(n):
                        ans.append(self.port.read_until(CRLF))

                elif extra_output:
                    ans = (ans, self.port.read_until(CRLF))

                else:
                    ans = int(ans.split(b' ')[1])
                return ans

            #getter = types.MethodType(getter, self, FringeCounter)
            setattr(self, "get_" + name, getter)
        if 'T' in mode:

            def func():
                cmd = f'T {addr: 02d} 0'
                ans = self.send_cmd(cmd)
                if extra_output:
                    ans = (ans, self.port.read_until(CRLF))
                else:
                    ans = ans
                return ans

            #getter = types.MethodType(getter, self, FringeCounter)
            setattr(self, name, func)


if __name__ == '__main__':
    import struct
    import time
    a = FringeCounter()
    print(dir(a))
    #    print(a.get_pd1_offset())
    #    print(a.get_pd2_offset())
    #    print(a.get_counter_value())
    print(a.start_offset_calc())
    time.sleep(5)
    print(a.stop_offset_calc())
    #a.set_pd1_offset(150)
    #a.set_pd2_offset(150)
    print(a.get_pd1_offset())
    print(a.get_pd2_offset())
    print(a.get_pd1_score_list())
    time.sleep(0.01)
    #print(a.get_counter_value())
    time.sleep(0.01)

    a.set_target_counts(100)

    for i in range(3):
        b = a.get_counter_table()
        #print(a.get_target_counts())
        time.sleep(0.2)
    print(b[1][:-2])
    print(struct.unpack('100h', b[1][:-2]))
