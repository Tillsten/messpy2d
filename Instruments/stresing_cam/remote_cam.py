# -*- coding: utf-8 -*-
"""
Created on Thu Feb 28 14:57:38 2019

@author: localadmin
"""
from nice_lib_back import Cam


import numpy  as np
import Pyro4
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.SERIALIZERS_ACCEPTED = set(['pickle','json', 'marshal', 'serpent'])


#cam = Cam()
@Pyro4.behavior(instance_mode="percall")
@Pyro4.expose
class PyroCam(Cam):
    pass

Pyro4.Daemon.serveSimple({
    PyroCam: 'Cam',
}, host="130.133.30.235", port=9090, ns=False, verbose=True)