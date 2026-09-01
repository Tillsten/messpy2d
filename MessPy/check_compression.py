# %%
import pathlib

import h5py

# %%
fn = list(pathlib.Path("c:/results/").glob("*.h5"))[-1]


# %%
with h5py.File(fn, "a") as f:
    a = f["full_data/MockCam/scan_1/t_ 0013"]
    a = a[:]

# %%
with h5py.File("c:/results/test2.h5", "a") as f2:
    for chunks in [(1, 3000, 10), True]:
        print(chunks)
        if "test2" in f2:
            del f2["test2"]
        f2.create_dataset(
            "test2",
            data=a[:],
            compression="lzf",
            chunks=chunks,
            shuffle=True,
            scaleoffset=2,
            # compression_opts=4,
        )
        print(abs((f2["test2"] - a) / a).mean())
        print(f2["test2"].id.get_storage_size() / a.nbytes)
        b = f2["test2"][:]
# %%
a.shape
# %%

sig = 1000 * np.log10(a[:, ::2, :].mean(1) / a[:, 1::2, :].mean(1))
sig2 = 1000 * np.log10(b[:, ::2, :].mean(1) / b[:, 1::2, :].mean(1))
import matplotlib.pyplot as plt

# %%
# plt.plot(sig2[0])
# plt.plot(sig[0])
plt.plot((sig2 - sig)[0])
# %%
