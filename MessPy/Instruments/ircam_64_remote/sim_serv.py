import numpy as np
import zmq

ctx = zmq.Context()
socket = ctx.socket(zmq.REP)
socket.bind('tcp://*:8001')
shots = 100

while True:
    cmd, val = socket.recv_pyobj()
    print(cmd, val)
    if cmd == 'set_shots':
        shots = int(val)
        socket.send_pyobj(val)
    elif cmd == 'read_cam':
        arr = np.random.randint(0, 2 << 16, (shots, 80))

        socket.send_pyobj(arr)


