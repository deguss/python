import pdb
import numpy as np
import matplotlib.pyplot as plt
import pyvisa
rm = pyvisa.ResourceManager()

ip = "192.168.1.12"

def get_max():
    s = scope.query("C1:PAVA? MAX")
    if (',OK\n' in s):
        return float(s.split(',')[1])
    elif (',OU\n' in s or ',OF\n' in s):
        return np.PINF
    
def get_min():
    s = scope.query("C1:PAVA? MIN")
    if (',OK\n' in s):
        return float(s.split(',')[1])
    elif (',OU\n' in s or ',OF\n' in s):
        return np.NINF

try:
    scope = rm.open_resource("VICP::"+ip+"::INSTR")
    print(scope.query("*IDN?"))
    scope.write("MSG 'running "+__file__+"'")
    scope.write("COMM_HEADER OFF")

except:
    print("could not connect on "+ip)
    rm.close()
    exit()

try:
    c1 = scope.query_binary_values("C1:WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
except:
    print("could not transfer waveform")

try:
    t_len = float(scope.query("TDIV?"))*10
    t = np.linspace(0, t_len, len(c1))    
    f = (get_max()-get_min())/(max(c1)-min(c1))
    print("factor to scale: 1/f="+str(1/f))
    
    plt.plot(t, f*c1, color='gold')
    plt.show()
except:
    pdb.set_trace()
    

    
rm.close()




