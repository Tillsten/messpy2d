"""
Created on Tue Feb 18 17:18:17 2014

@author: tillsten
"""
from pyface.timer.api import Timer

#import sfml
from serial import Serial
from traits.api import *
from traitsui.api import Group, Item, View


class SingleFaulhaber:
    def __init__(self, comport, s2mm):
        self.ser = Serial(comport, baudrate=9600*12)
        self.ser.timeout = 0.1
        self.motor_init()
        self.step2mm = s2mm        
        self.is_binsend = False
        
    def motor_init(self):
        write = self.ser.write
        write(b'en\r')
        write(b'answ1\r')
        write(b'AC30000\r')
        write(b'DEC30000\r')

    def set_vel(self, m1_vel=0):
        cmd = f'v{m1_vel:d}\r'
        self.ser.write(cmd.encode())

    def set_pos(self, pos, wait_for_move=True):
        cmd = f'la{pos:f}\r'
        if wait_for_move:
            self.ser.write(b'NP\r')
        self.ser.write(cmd.encode())
        self.ser.write(b'M\r')
        if wait_for_move:
            tmp = self.ser.timeout
            self.ser.timeout = 2
            print( ":", self.ser.readline())
            #self.ser.readline()
            self.ser.timeout = tmp

    def get_pos(self):
        self.ser.write(b'pos\r')
        try:
            pos1 = int(self.ser.readline()[:-2])
        except ValueError:
            pos1 = 0
            
        return pos1
        
    def get_pos_mm(self):
        pos = self.get_pos()
        return pos * self.step2mm

    def set_pos_mm(self, pos_mm, wait_for_move=True):
        pos = pos_mm/self.step2mm
        self.set_pos(pos, wait_for_move)
        
    def is_moving(self):
        self.ser.write(b'GV\r')
        m1 = self.ser.readline()[:-2]
        if float(m1.decode()) < 3:
            return False
        else:
            return True
            
    def enable_binmode(self):
        self.is_binsend = True
        self.ser.write(b'BINSEND1\r')
        self.ser.write(''.join([chr(200), chr(200), chr(202), chr(201)]))
    
    def read_bin(self):
        self.ser.write(''.join([chr(201)]))
        ans = self.ser.read(9)
        



    def set_home(self):
        self.ser.write(b'HO\r')
        
    def motor_disable(self):
        self.ser.write(b'DI\r')
        
class XYSingleFaulhaber:
    def __init__(self):
        self.x_mot = SingleFaulhaber(s2mm=5e-5, comport='COM6')
        self.y_mot = SingleFaulhaber(s2mm=3.6e-5, comport='COM5')

    def motor_init(self):
        self.x_mot.motor_init()
        self.y_mot.motor_init()
        
    def set_vel(self, x, y):
        self.x_mot.set_vel(x)
        self.y_mot.set_vel(y)
        
    def get_pos(self):
        return self.x_mot.get_pos(), self.y_mot.get_pos()
    
    def get_pos_mm(self):
        return self.x_mot.get_pos_mm(), self.y_mot.get_pos_mm()

    def set_pos(self, x=None, y=None, wait_for_move=False):
        if x is not None:
            self.x_mot.set_pos(x, wait_for_move=False)
        if y is not None:
            self.y_mot.set_pos(y, wait_for_move=False)
        if wait_for_move:
            if x is not None:
                self.x_mot.set_pos(x, wait_for_move=True)
            if y:
                self.y_mot.set_pos(y, wait_for_move=True)
    
    def set_pos_mm(self, x=None, y=None, wait_for_move=False):        
        if x is not None:
            self.x_mot.set_pos_mm(x, wait_for_move=False)
        if y is not None:
            self.y_mot.set_pos_mm(y, wait_for_move=False)
        if wait_for_move:
            if x is not None:
                self.x_mot.set_pos_mm(x, wait_for_move=True)
            if y is not None:
                self.y_mot.set_pos_mm(y, wait_for_move=True)
    
    def is_moving(self):
        return self.x_mot.is_moving() or self.y_mot.is_moving()

    def is_xy_moving(self):
        return self.x_mot.is_moving(), self.y_mot.is_moving()
        
    def set_home(self):
        self.x_mot.set_home()
        self.y_mot.set_home()
        
    def motor_disable(self):
        self.x_mot.motor_disable()
        self.y_mot.motor_disable()
        
class Faulhaber:
    def __init__(self, comport=1):
        self.ser = Serial(comport, xonxoff=False, baudrate=12*9600)
        self.ser.timeout = 0.05
        self.motor_init()
        #self.ser = sys.stdout

    def motor_init(self):
        write = self.ser.write
        write(b'1en\r')
        write(b'2en\r')
        write(b'1AC30000\r')
        write(b'1DEC30000\r')
        write(b'2AC30000\r')
        write(b'2DEC30000\r')
        write(b'1answ1\r')
        write(b'2answ1\r')


    def motor_disable(self):
        self.ser.write(b'1di\r')
        self.ser.write(b'2di\r')

    def set_vel(self, m1_vel=0, m2_vel=0):
        cmd = f'1v{m1_vel:d}\r2v{m2_vel:d}\r'
        self.ser.write(cmd.encode())
        #self.ser.write('M\r')

    def set_pos(self, m1_pos=None, m2_pos=None, wait_for_move=True):
        cmd = ''
        if  m1_pos is not None:
            cmd += f'1la{m1_pos:.2f}\r'
        if  m2_pos is not None:
            cmd += f'2la{m2_pos:.2f}\r'
        #print cmd
        self.ser.write(cmd.encode())
        if wait_for_move:
            self.ser.write(b'NP\r')
        self.ser.write(b'M\r')
        if wait_for_move:
            tmp = self.ser.timeout
            self.ser.timeout = 0.5
            #print( ":", self.ser.readline())
            self.ser.readline()
            self.ser.timeout = tmp

    def set_pos_mm(self, m1_pos=None, m2_pos=None, wait_for_move=True):
        if m1_pos is not None:
            x_step = m1_pos / 5e-5
        else:
            x_step = None
        if m2_pos is not None:
            y_step = m2_pos / 3.6e-5
        else:
            y_step = None
        self.set_pos(x_step, y_step, wait_for_move)

    def get_pos_mm(self):
        x, y = self.get_pos()
        return x * 5e-5, y* 3.6e-5

    def is_moving(self):
        self.ser.write(b'1GV\r')
        m1 = self.ser.readline()
        self.ser.write(b'2GV\r')
        m2 = self.ser.readline()
        try: 
            m1 = float(m1)
            m2 = float(m2)
            return m1 < 3 and m2 <3 
        except ValueError:
            return False
        

    def get_pos(self):
        try:
            self.ser.write(b'1pos\r')
            x = self.ser.readline()
            print('pos1', x)
            pos1 = int(x[:-2])

            self.ser.write(b'2pos\r')
            x = self.ser.readline()
            print('pos2', x)
            pos1 = int(x[:-2])
            return pos1, pos2
        except:
            return 0, 0


    def set_home(self):
        self.ser.write(b'2HO\r')
        self.ser.write(b'1HO\r')


"""
#class Joystick(HasTraits):

#    joystick_id = Int(0)

#    x_pos = Float(0)
#    y_pos = Float(0)
#    pov_x = Float(0)
#    pov_y = Float(0)


#    but_1 = Bool(False)
#    but_2 = Bool(False)
#    but_3 = Bool(False)
#    but_4 = Bool(False)

 #   def update(self):
#        joystick_id = self.joystick_id
#        sfml.Joystick.update()

#        self.x_pos = sfml.Joystick.get_axis_position(joystick_id, 0)
#        self.y_pos = sfml.Joystick.get_axis_position(joystick_id, 1)
        # DPAD
#        self.pov_x = sfml.Joystick.get_axis_position(joystick_id, 6)
#        self.pov_y = sfml.Joystick.get_axis_position(joystick_id, 7)

#        self.but_1 = sfml.Joystick.is_button_pressed(joystick_id, 0)
#        self.but_2 = sfml.Joystick.is_button_pressed(joystick_id, 1)
#        self.but_3 = sfml.Joystick.is_button_pressed(joystick_id, 2)
#        self.but_4 = sfml.Joystick.is_button_pressed(joystick_id, 3)


class FaulhaberControl(HasTraits):
    pos_x = Int(0)
    pos_y = Int(0)

    pos_x_mm = Property(Float, depends_on='pos_x')
    pos_y_mm = Property(Float, depends_on='pos_y')

    def _get_pos_x_mm(self):
        return self.pos_x * 5e-5

    def _get_pos_y_mm(self):
        return self.pos_y * 3.6e-5

    set_pos_x = Float(0)
    set_pos_y = Float(0)

    x_vel = Int(0)

    y_vel = Int(0)
    def set_pos_mm(self, m1_pos=None, m2_pos=None, wait_for_move=True):
        if m1_pos is not None:
            x_step = m1_pos / 5e-5
        else:
            x_step = None
        if m2_pos is not None:
            y_step = m2_pos / 3.6e-5
        else:
            y_step = None
        self.set_pos(x_step, y_step, wait_for_move)

    m1_maxvel = Int(10000)
    m2_maxvel = Int(10000)

    move_to = Button()
    define_home = Button()
    fh = Instance(Faulhaber)
    joy = Instance(Joystick)
    but1_pressed = Event

    timer = Any
    moving = Bool(False)
    update_rate = 1

    def _moving_changed(self, val):
        self.on_trait_change(self.move, 'joy.x_pos, joy.y_pos', remove=not val)
    def set_pos_mm(self, m1_pos=None, m2_pos=None, wait_for_move=True):
        if m1_pos is not None:
            x_step = m1_pos / 5e-5
        else:
            x_step = None
        if m2_pos is not None:
            y_step = m2_pos / 3.6e-5
        else:
            y_step = None
        self.set_pos(x_step, y_step, wait_for_move)

    def update(self):
        x, y = fh.get_pos()
        self.pos_x, self.pos_y = x, y
        self.joy.update()

    @on_trait_change('joy.pov_x, joy.pov_y')
    def step(self, ch):
        x, y = self.joy.pov_x, self.joy.pov_y
        print( x, y)
        if abs(x) > 50. or abs(y) > 50.:
            self.fh.set_pos(int(x*2 + self.pos_x),
                            int(y*2 + self.pos_y), 0)

    def move(self, change):
        DEADZONE = 1
        x, y = self.joy.x_pos, self.joy.y_pos
        if abs(x) > DEADZONE:
            self.x_vel = int(x/float(100-DEADZONE) * self.m1_maxvel)
        else:
            self.x_vel = 0
        if abs(y) > DEADZONE:
            self.y_vel = int(y/float(100-DEADZONE) * self.m2_maxvel)
        else:
            self.y_vel = 0

        self.fh.set_vel(self.x_vel, self.y_vel)

    def _define_home_fired(self):
        self.fh.set_home()

    def _move_to_fired(self):
        print( self.set_pos_x, self.set_pos_y)
        #self.timer.stop()
        self.fh.set_pos_mm(self.set_pos_x, self.set_pos_y)
        #self.timer.start()
    @on_trait_change('joy.but_3')
    def inc_maxvel(self, new_val):
        print( "pressed")
        if not new_val:
            return
        self.m1_maxvel *= 3
        self.m2_maxvel *= 3

    @on_trait_change('joy.but_4')
    def dec_maxvel(self, new_val):
        if not new_val:
            return
        self.m1_maxvel /= 3
        self.m2_maxvel /= 3

    @on_trait_change('joy.but_1')
    def fire_but1_pressed(self, new_val):
        if new_val:
            self.but1_pressed = True

    def __init__(self, **kwargs):
        HasTraits.__init__(self, **kwargs)
        self.timer = Timer(self.update_rate, self.update)

    info_group = ['pos_x', 'x_vel',
                  'pos_x_mm', '_',
                  'pos_y', 'y_vel',
                  'pos_y_mm']
    info_group = map(lambda x: Item(x, style='readonly'), info_group)
    traits_view = View(Group(info_group + ['_',
                               'set_pos_x', 'set_pos_y',
                               'm1_maxvel', 'm2_maxvel',
                               'moving', 'define_home', 'move_to'
                              ]))

"""


if __name__ == '__main__':
#    joy = Joystick(joystick_id=0)
    #fhc = FaulhaberControl(joy=joy, fh=fh)
    #fhc.moving = True
    #fhc.configure_traits()
    fh = XYSingleFaulhaber()
    from time import sleep, time
    t0 = time()
    from math import cos, pi, sin
    x_amp = 5/2.
    y_amp = 3/2.

    while True:
        t = time() - t0
        x = x_amp * cos(1.2*t*2*pi)
        y = y_amp * cos(1.5*t*2*pi)
        fh.set_pos_mm(x, y, wait_for_move=False)
        sleep(0.02)
        fh.x_mot.ser.flush()
