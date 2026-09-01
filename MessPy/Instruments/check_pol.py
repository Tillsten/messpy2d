# %%
import matplotlib.pyplot as plt
import numpy as np

poldata = """0	190
20	198
40	179
60	126
80	57
100	24
120	50
140	103
160	156
180	190
200	202
220	176
240	125
260	55
280	21
300	47
320	105
340	158
"""


poldata = np.array(
    [list(map(float, line.split())) for line in poldata.split("\n") if line]
)

# %%
plt.plot(poldata[:, 0], poldata[:, 1])
# %%
import lmfit


# %%
def fit_func(x, a, b, c):
    return a * np.sin(2 * np.deg2rad(x + c)) + b


model = lmfit.Model(fit_func)
params = model.make_params(a=100, b=125, c=-20)
result = model.fit(poldata[:, 1], params, x=poldata[:, 0], method="least_squares")
# %%#
# result.plot_fit(numpoints=300)
result.plot()
# %%
result.conf_interval()


# %%
import math

LOG10 = math.log(10)


def fast_signal(arr) -> float:
    """
    For a given 1-dimensional array calculate the signal.
    """
    sig = 0
    mean = 0
    n = arr.shape[0]

    for i in range(0, n, 2):
        sig += arr[i] - arr[i + 1]
        mean += arr[i] + arr[i + 1]
    mean /= n
    return 1000 / LOG10 * np.log1p(sig / mean)
