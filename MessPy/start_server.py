

#from shutter import sh
#from MessPy.Instruments.RotationStage import rs
import threading
import xmlrpc.server

from MessPy.Instruments.delay_line_mercury import _dl
from MessPy.Instruments.sample_holder_PI import SampleHolder

thr = SampleHolder.create_remote(('', 8001), 'thread')
thr.start()

if __name__ == '__main__':
    server_dl = xmlrpc.server.SimpleXMLRPCServer(('', 8000))
    server_dl.register_instance(_dl)
    print("DelayLine server started")
    t = threading.Thread(target=server_dl.serve_forever)
    t.start()

    #server_rs = xmlrpc.server.SimpleXMLRPCServer(('', 8003), allow_none=True)
    # server_rs.register_introspection_functions()
    # server_rs.register_instance(rs)
    #print("Rotationstage server started")
    #t = threading.Thread(target=server_rs.serve_forever)
    # t.start()

    #server_sh = xmlrpc.server.SimpleXMLRPCServer(('', 8002), allow_none=True)
    # server_sh.register_introspection_functions()
    # server_sh.register_instance(sh)
    #print("Shutter server started")
    #t = threading.Thread(target=server_sh.serve_forever)
    # t.start()
