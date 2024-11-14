import tldevice
import time
from datetime import datetime
import pdb
import numpy as np

now = datetime.now()
current_time = now.strftime("%H:%M:%S")
# csak hogy az idot is kiirja

magn = tldevice.Device("COM3") #atirni
magn.mode.axis.x(1)
# magn.field.data.active = 1

fold = r"C:\Users\Zsofi\Desktop\Twinleaf"
filename = fold + r"\vector_meas_ZBL_0704.txt" # + current_time + ".txt"

k=open(filename, "a+")
k.close()
LEN = 500
x = np.arange(LEN)
y = np.arange(LEN)
i=0

while True:   
        
        field_data = magn.vector() # skalar magnetometernel ez a parancs irja ki a mezo erteket
        
        x[i] = field_data[0]
        y[i] = field_data[1]
        
        #print(f'{field_data[0]}, {field_data[1]}, s:{magn.status()}')
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        k=open(filename, "a+")
        k.write("{0};{1}\n".format(current_time,field_data))
        k.close()
        
        i+=1
        if (i>=LEN):
            print(f'x = {np.median(x)} \ty = {np.mean(y)}, \ts:{magn.status()}')
            x = np.arange(LEN)
            y = np.arange(LEN)
            i=0
        
        #time.sleep(5) # 5 mp pihi       e
        #pdb.set_trace()