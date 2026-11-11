# %%
import ctypes as ct

import cppyy

 # %%
cppyy.load_library(r"C:\Program Files (x86)\Signatec\PXDAC4800\Lib64\PXDAC4800_64.dll")
cppyy.add_include_path(r'C:\Program Files (x86)\Signatec\PXDAC4800\Include')
cppyy.include('pxdac4800.h')


# %%
cppyy.gbl.GetDeviceCountXD48()
# %%
# Obtain a handle to a local PXDAC4800 device
hdl = ct.pointer(ct.c_ulong())

# %%
cppyy.gbl.ConnectToDeviceXD48(hdl, 1);



# %%
out = ct.c_uint()
ret =  cppyy.gbl.GetSerialNumberXD48(hdl, ct.byref(out))
out.value, ret
# %%
buf = ct.create_string_buffer(1000)
cppyy.gbl._GetBoardNameAXD48(hdl,  buf, 0)
# %%
cppyy.gbl.IsHandleValidXD48(hdl)
d = ct.c_double()
cppyy.gbl.GetPlaybackClockRateXD48(hdl, d);
d.value
# %%
cppyy.gbl.SetActiveChannelMaskXD48(hdl, 0x1|0x2)
# %%
cppyy.gbl.EndRamPlaybackXD48(hdl)
# %%

cppyy.gbl.GetActiveChannelMaskXD48(hdl)
# %%
cppyy.gbl.GetDacSampleFormatXD48(hdl)
# %%
cppyy.gbl.SetTriggerModeXD48(hdl, 0) 
cppyy.gbl.GetExternalTriggerEnableXD48(hdl)
# 1 = signed
cppyy.gbl.GetDacSampleSizeXD48(hdl)
cppyy.gbl.SetDacSampleSizeXD48(hdl, 2)
# %%
"""XD48API LoadRamBufXD48 (HXD48 hBrd, 
						unsigned int offset_bytes, 
						unsigned int length_bytes,
						const void*  bufp,
						int bAsynchronous _XD48_DEF(0));
                        """

masks = 4
import numpy as np

buf = (1<<15-1)*np.sin(2*np.pi*np.arange(4096*3)/16)
#buf = np.hstack(buf, buf))
buf = np.tile(buf, masks)
buf2 = np.tile((1<<15-1)*np.ones(4096*3, dtype=np.int16), masks)
buf2[4096*3:] = 0

#out = np.zeros(masks*120000*2, dtype=np.int16)
#out[::2] = 1<<8
#out.size
import matplotlib.pyplot as plt

bufi = buf.astype('int16')

dual_buf = np.empty(buf.size*2, dtype=np.int16)
dual_buf[::2] =  bufi
dual_buf[1::2] =  buf2

plt.plot(dual_buf[::2])
plt.plot(dual_buf[1::2])
with open('myfile.rd16', 'wb') as f:
	f.write(dual_buf.tobytes())
plt.xlim(0, 32)
plt.show()
# %%
"""int InterleaveData16bit2ChanXD48 (
const unsigned short* src_ch1p,
const unsigned short* src_ch2p,
unsigned int samps_per_chan,
unsigned short* dstp);"""
#cppyy.gbl.InterleaveData16bit2ChanXD48(bufi.data, buf2.data, 4096*3, dual_buf.data)

cppyy.gbl.EndRamPlaybackXD48(hdl)
cppyy.gbl.LoadRamBufXD48(hdl, 0, dual_buf.size*2, dual_buf.data, 0)

# %%
#plt.plot(dual_buf[::2])
#plt.xlim(0, 32)
#plt.show()
# %%

cppyy.gbl.BeginRamPlaybackXD48(hdl, 0, dual_buf.size*2, 4096*3)

# %%
cppyy.gbl.IssueSoftwareTriggerXD48(hdl)

# %%
