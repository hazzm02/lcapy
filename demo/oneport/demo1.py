from lcapy import Vstep, R, L, C
import numpy as np
from matplotlib.pyplot import figure, savefig, show

a = (Vstep(5) + R(10)) | C(1)

t = np.linspace(0, 10, 1000)

fig = figure()
ax = fig.add_subplot(111)
ax.plot(t, a.v.evaluate(t), linewidth=2)
ax.set_xlabel('Time (s)')
ax.set_ylabel('Voltage (V)')
ax.grid(True)

show()
