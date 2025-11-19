# %%
import math
import numpy as np

from numpy.typing import NDArray
from numba import njit, prange

LOG10 = math.log(10)


def classic_signal(a: NDArray[np.float64]) -> float:
    return np.log10(a[:-1:2].mean() / a[1::2].mean()) * 1000


@njit(cache=True, fastmath=True)
def fast_signal(arr: NDArray[np.float64]) -> float:
    """
    For a given 1-dimensional array calculate the signal.
    """
    sig = 0
    mean = 0
    n = arr.shape[0]

    for i in range(0, n):
        if i % 2 == 0:
            sig += arr[i]
        else:
            sig -= arr[i]
        mean += arr[i]

    #print(sig, mean)
    return 1000 * np.log10((mean+sig)/(mean-sig))


@njit(cache=True, fastmath=True)
def fast_signal2(arr: NDArray[np.float64]) -> float:
    """
    For a given 1-dimensional array calculate the signal.
    """
    sig = 0.
    mean = 0.
    n = arr.shape[0]

    for i in range(0, n):
        sig += arr[i] if i % 2 == 0 else -arr[i]
        mean += arr[i]
    return 1000 * np.log10((mean+sig)/(mean-sig))


@njit(cache=True, fastmath=True)
def fast_signal3(arr: NDArray[np.float64]) -> float:
    """
    For a given 1-dimensional array calculate the signal.
    """
    sig = 0.
    mean = 0.
    n = arr.shape[0]

    for i in range(0, n, 2):
        sig += arr[i]
        mean += arr[i+1]
    return -1000 * np.log10((mean/sig))

import matplotlib.pyplot as plt

out = []
for sig_size in np.linspace(-0.15, 0.15, 20):
    x = 1000 + 3 * np.random.normal(size=(128, 10000))
    x[0, ::2] *= 1 + sig_size
    y1 = classic_signal(x[0, :])
    y2 = fast_signal(x[0, :])
    y3 = fast_signal3(x[0, :])

    out.append((sig_size, y1, y2, y3))
out = np.array(out)
plt.plot(out[:, 0], out[:, 1], label="classic")
plt.plot(out[:, 0], out[:, 2], label="fast")
plt.plot(out[:, 0], out[:, 3], label="fast")

plt.plot(out[:, 0], (out[:, 1] - out[:, 2]) * 10, label="diff")

plt.figure()
plt.plot(out[:, 0], out[:, 1] / out[:, 2], label="diff")
# %%
%timeit fast_signal(x[0, :])
%timeit fast_signal2(x[0, :])
%timeit fast_signal3(x[0, :])
# %%
%timeit classic_signal(x[0, :])
# %%
