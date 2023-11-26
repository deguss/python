#from os import listdir, path
import matplotlib.pyplot as plt
import numpy as np
import time
from sys import exit
#from datetime import datetime, timedelta
import struct
from tkinter import *
import collections
#import os
import pdb
#from memory_profiler import profile

DATALEN=180
ports=[]
d_inp=collections.deque(maxlen=DATALEN) #create a circular buffer


def portChoice(*args):
    # this is the callback function of the dialog window
    # when valid com port is selected, it closes the window
    
    idxs = lbox.curselection()
    if(len(idxs)==1):
        p=ports[int(idxs[0])]
        #print(p+" selected")
        root.quit()
        root.destroy()

        if(openSerial(p.split()[0]) == False):
            plt.close()
            exit("No data received. Right port? Instrument turned on?")
    else:
        print("please select 1 valid COM port")
    
    
 

def openSerial(p):
    # opens the serial port  p and listens to values sent by the instrument
    timeout=0
    print("opening "+p)
    import serial
    with serial.Serial(p, 57600, timeout=3,  rtscts=1 ) as ser:
        ser.reset_input_buffer()
        while True:
            if (ser.inWaiting() > 20):
                f=float(ser.readline())
                #print(f)
                updatePlot(f)
                timeout=0
            else:
                timeout += 1
                time.sleep(0.1)
                if (timeout>30):
                    return False

def updatePlot(f):
    global d_inp, line1, fig

    d_inp.append(f)
    #print('d_inp[{}]={}' .format(idx, f))
    
    line1.set_xdata(np.linspace(0,len(d_inp),len(d_inp)))
    line1.set_ydata(d_inp)
    
    ax=plt.gca()
    ax.relim()
    ax.autoscale_view()
    
    fig.canvas.draw()
    fig.canvas.flush_events()
    


if __name__ == "__main__":
    

    from serial.tools.list_ports import comports
    for port in comports():
        ports.append(str(port))

    print ("Choose COM port in the dialog window!")

    #open a dialog window to ask for COM port 
    root = Tk()
    root.geometry("320x200+300+300")
    root.title("Choose COM port!")
    
    choicesvar = StringVar(value=ports)
    lbox = Listbox(root, listvariable=choicesvar, width=80, height=6)
    lbox.bind("<Double-1>", portChoice)
    lbox.pack()

    okButton = Button(root, text="open", command=portChoice)
    okButton.place(x=160, y=100)

    # Create a new figure, plot into it, then close it so it never gets displayed
    plt.ion() #turn interactive plotting off
    fig = plt.figure()
    ax = fig.add_subplot(111)
    line1, = ax.plot(0, 0, '.r') # Returns a tuple of line objects, thus the comma
    #plt.close()
    

    
    root.mainloop()   



