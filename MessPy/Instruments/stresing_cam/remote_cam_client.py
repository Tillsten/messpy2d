"""
Created on Fri Mar  1 16:02:27 2019

@author: localadmin
"""
import Pyro4

Pyro4.config.SERIALIZER = 'pickle'
ip = '127.0.0.1'
ip = '130.133.30.235'
cam = Pyro4.core.Proxy('PYRO:Cam@' + ip + ':9090')
print(cam)



