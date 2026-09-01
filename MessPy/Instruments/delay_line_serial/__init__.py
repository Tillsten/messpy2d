import serial


class DelayLine:
    def __init__(self):
        port = 'COM10'
        self.port = serial.Serial(port, baudrate=9600*12, rtscts=True)
        self.moving = False
        self.name = f'Remote DelayLine {port} '

    def move_fs(self, pos_fs, do_wait=True):
        self.port.flushInput()
        x = ('M'+str(pos_fs)+'\n').encode()
        #print(x)
        self.port.write(x)
        self.port.timeout = 3
        self.moving = True
        while True:
            ans = self.port.readline()
            if ans == "":
                break
            #print(ans)
            if ans == b'DONE\n':
                break
            if ans == b'RESEND\n' or ans == b'':
                self.port.write(x)
        self.moving = False
                
    def def_home(self):
        self.port.write(b'DH\n')

    def get_pos_fs(self):
        self.port.timeout = 0.1
        self.port.write(b'GP\n')
        try:
            pos = float(self.port.readline()[:-1])
        except ValueError:
            pos = 0
        self.port.timeout = None
        return pos

    def shutdown(self):
        self.port.close()

dl = DelayLine()

