import numpy as np
from pyqtgraph.parametertree.parameterTypes import GroupParameter


class DelayParameter(GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'list'
        opts['value'] = True
        if "name" not in opts:
            opts['name'] = 'Delay Times'
        GroupParameter.__init__(self, **opts)
        time_parameters = [{'name': 'Linear Range (-)', 'suffix': 'ps', 'type': 'float', 'value': -1, 'step': 0.05},
                           {'name': 'Linear Range (+)', 'suffix': 'ps', 'type': 'float', 'value': 1, 'step': 0.05},
                           {'name': 'Linear Range (step)', 'suffix': 'ps', 'type': 'float', 'min': 0.001, 'value': 0.1, 'step': 0.05},
                           {'name': 'Logarithmic Scan', 'type': 'bool', 'value': False},
                           {'name': 'Logarithmic End', 'type': 'float', 'suffix': 'ps', 
                            'min': 0.1, 'value':100},
                           {'name': 'Logarithmic Points', 'type': 'int', 'min': 0, 'value': 20},
                           dict(name="Add pre-zero times", type='bool', value=False),
                           dict(name="Num pre-zero points", type='int', value=10, min=0, max=20),
                           dict(name="Pre-Zero pos", type='float', value=-60., suffix='ps'),
                           dict(name='Time-points', type='str', readonly=True, value=''),
                           ]
        self.addChildren(time_parameters)
        self.out_str = self.child('Time-points')
        self.sigTreeStateChanged.connect(self.format_values)
        self.t_list = []

    def generate_values(self, *args) -> list[float]:
        p = self
        t_list = np.arange(p['Linear Range (-)'],
                           p['Linear Range (+)'],
                           p['Linear Range (step)']).tolist()
        if p['Logarithmic Scan']:
            t_list += (np.geomspace(p['Linear Range (+)'], p['Logarithmic End'], p['Logarithmic Points']).tolist())

        if p['Add pre-zero times']:
            n = p['Num pre-zero points']
            pos = p['Pre-Zero pos']
            times = np.linspace(pos - 1, pos, n).tolist()
            t_list = times + t_list
        self.t_list = t_list
        return t_list

    def format_values(self, *args) -> None:
        self.generate_values()
        out_str = f"Time-points: {len(self.t_list)}"
        #for k, v in enumerate(self.t_list):
        #    if (k % 5 == 0) and k > 0:
        #        out_str += "\n"
        #    out_str += "%-8.2f " % v
        self.out_str.setValue(out_str)
