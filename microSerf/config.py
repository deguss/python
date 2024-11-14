#!/usr/bin/env python3
import pdb
import time 
import tldevice
serf = tldevice.Device(url="COM13")
if (serf.mode.axis.x() == 0):
    serf.mode.axis.x(1)
if (serf.data.rate() != 20):
    serf.data.rate(20)
serf.coil.x.test.enable(1)
serf.coil.y.test.enable(1)

status = 0
#wait until "3 Field zeroing failed" or "7 Calibrated"
while(status != 3 and status != 7):
    status = serf.status()
    print(f'status = {status}, waiting...')


c = ""
try:
    while c != '\n':
        print("\nperforming zeroing and calibration")
        print("status = ",end="")
        serf.auto.zero()
        status = 0
        while (status != 7):
            status = serf.status()
            print(f'{status}', end=" ")
        print(" ")        
        print(f'COIL.field  x = {(serf.coil.x.field()*1e3):9.2f}nT\ty = {(serf.coil.y.field()*1e3):9.2f}nT\t'\
              f'laser = {serf.status.laser()*100:4.1f}%')
        for i in range(5):
            print(f'LASER.field x = {serf.vector()[0]:9.2f}nT,\ty = {serf.vector()[1]:9.2f}nT') 
        c = input("Press [Enter] to repeat   \t[Ctrl+C] to quit\t [Ctrl+D] to debug")
except EOFError:    #triggered Ctrl+D
    pdb.set_trace()
except KeyboardInterrupt: #triggered Ctrl+C
    pass
serf.status.laser()

"""
file = open('log.tsv','w') 
for row in serf.data.iter():
  rowstring = "\t".join(map(str,row))+"\n"
  file.write(rowstring)
"""
