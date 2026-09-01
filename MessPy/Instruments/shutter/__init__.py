"""
Implements communication to the the shutter
controller form thorlabs.
"""
import serial


class Shutter:
    def __init__(self, com_port=1):
        """
        Shutter object to control the shutter.

        Parameters
        ----------

        com_port - int (default=1)
           the serial port which connects to the sc10.
        """
        self.port = serial.Serial(com_port, timeout=0.1)
        self.port.read(1)


    def is_open(self):
        """
        Check if shutter is open.
        """
        self.port.flushInput()
        self.port.write(b'ens?\r')
        ans = self.port.read(6)

        if ans[-1:] == b'1':
            return True
        else:
            return False

    def toggle(self):
        """
        Toggle the shutter state.
        """
        self.port.write(b'ens\r')
        self.port.read(4)


    def open(self):
        if not self.is_open():
            self.toggle()

    def close(self):
        if self.is_open():
            self.toggle()

sh = Shutter('COM8')

if __name__ == '__main__':

    try:
        print(sh.is_open())
        sh.open()
        sh.close()
    except:
        raise
    finally:        
        sh.port.close()