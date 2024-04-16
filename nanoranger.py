import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
import collections
import math
import datetime as dt

from engfmt import Quantity, quant_to_eng
import time, threading
CALLBACK_SECONDS = 1
BUFFERSIZE=3600*3
from serial.tools.list_ports import comports
import serial

#----------------------------------------------------------
class NanoRanger(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)   
        self.parent = parent
        
        self.timeout=0
        self.tim=0
        self.resetBuf(BUFFERSIZE)
        self.ofname='nr_data'
        self.ofhandle=None
        
        self.ports=[]
        for port in comports():
            self.ports.append(str(port))
        
        self.initUI()

    def initUI(self):
        # create GUI inside parent frame
        self.pack(fill=tk.BOTH, expand=1)
        
        boxname = tk.Label(self, text="NanoRanger", font=("Arial", 16)) #title
        boxname.pack(padx=10, pady=10)

        self.openButton = tk.Button(self, text="open port", command=self.testSerPort)
        self.openButton.pack(padx=10, anchor=tk.E)

        self.closeButton = tk.Button(self, text="close port", command=self.serClose, state=tk.DISABLED) #combine_funcs())
        self.closeButton.pack(padx=10, anchor=tk.E)
        
        choicesvar = tk.StringVar(value=self.ports)
        self.lbox = tk.Listbox(self, listvariable=choicesvar, width=35, height=6, activestyle='none', font=("Courier", 10))
        self.lbox.bind("<Double-1>", self.testSerPort) #register doubleclick action
        self.lbox.pack(padx=10, pady=10)

        self.msgLabel = tk.Label(self, text="")
        self.msgLabel.pack(padx=10, anchor=tk.W)

        self.dispLabel = tk.Label(self, text="")
        self.dispLabel.pack(padx=10, anchor=tk.S)

 
    def testSerPort(self, *args):      
        idxs = self.lbox.curselection()
        if (self.isSerOpen() == False): #if not yet open
            if(len(idxs)==1):
                p=self.ports[int(idxs[0])]
                self.pr=p.split()[0]
                
                if(self.openSerial(self.pr) == False):
                    self.msg("No data received. Right port? Instrument turned on?")

            else:
                self.msg("please select a valid serial port!")

    def openSerial(self, p):
    # opens the serial port  p and listens to values sent by the instrument
        timeout=0
        self.ser = serial.Serial(p, 57600, timeout=3,  rtscts=1 )
        self.ser.reset_input_buffer()

        if (self.ser.is_open):
            self.msg(p+" opened")
            self.openButton.configure(state=tk.DISABLED)
            self.closeButton.configure(state=tk.NORMAL)
            self.lbox.configure(state=tk.DISABLED)
            self.timerCallBack()
            return True
        else:
            self.msg("Failed to open port "+p+"!")
            return False   


            
  
    def timerCallBack(self):
        if (self.ser.is_open):
            self.tim = threading.Timer(CALLBACK_SECONDS, self.timerCallBack)
            self.tim.start()
        
            while (self.ser.inWaiting() > 20):
                try:
                    f=float(self.ser.readline())
                    self.addSample(f)
                except(ValueError):
                    self.timeout +=1
                    self.msg("ValueError! data corrupt!")

                if (self.timeout):
                    self.timeout=0
                    self.msg(self.pr+" open")
            else:
                self.timeout += 1
                if (self.timeout > 1):
                    self.msg("Timeout! "+str(self.timeout))
        else:
            self.serClose()
            
        if (self.timeout > 5):
            self.timeout=0
            self.serClose()
            
    def saveButtonAction(self):
        if self.ofhandle == None:
            self.ofhandle = open(self.ofname+dt.datetime.strftime(dt.datetime.utcnow(),'%H%M')+'.txt','w')
            self.parent.saveButton.config(text='Stop saving data')
        else:
            self.ofhandle.close()
            self.ofhandle = None
            self.parent.saveButton.config(text='Start saving data')
        
    def addSample(self, f):
        self.cbuf.append(f)
        m=quant_to_eng(f,'A')
        self.dispLabel.configure(text=m)
        if self.ofhandle is not None:
            self.ofhandle.write('{} {}\n'.format(dt.datetime.utcnow(),f))

    def resetBuf(self, bufferSize):
        self.cbuf=collections.deque(maxlen=int(bufferSize)) #reinit circ buffer

    def getBuf(self):
        return np.array(list(self.cbuf))
        
    def msg(self, mess):
        self.msgLabel.config(text=mess)
        if '?' in mess or '!' in mess:
            self.msgLabel.config(fg="red")
        else:
            self.msgLabel.config(fg="green")

    def isSerOpen(self):
        if 'open' in self.msgLabel.cget("text"):
            try:
                if(self.ser.is_open):
                    return True
                else:
                    return False
            except:
                return False
        return False
        


    def serClose(self):
        if (self.tim.is_alive()):
            self.tim.cancel()
        if (self.isSerOpen()):
            self.ser.close()
            
        self.msg("port closed")
        self.lbox.configure(state=tk.NORMAL)
        self.openButton.configure(state=tk.NORMAL)
        self.closeButton.configure(state=tk.DISABLED)
        self.dispLabel.configure(text="")
        self.timeout=0
        self.resetBuf(BUFFERSIZE)
        self.idx=0


UPDATE_RATE = 1
class App():
    def __init__(self):
        self.running = 0
        self.window = tk.Tk()
        self.window.geometry("700x400")
        self.window.title("Explore NanoRanger")
        
        frame = tk.Frame(master=self.window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        frame.pack(side=tk.LEFT, padx=10, pady=10)
        self.nano = NanoRanger(frame)

        startButton = tk.Button(self.window, text="start real-time view", command=self.draw)
        startButton.pack(side=tk.BOTTOM, padx=10)

        startButton = tk.Button(self.window, text="stop", command=self.stop)
        startButton.pack(padx=10)
        
        frame.saveButton = tk.Button(self.window, text="Start saving data", command=self.nano.saveButtonAction)
        frame.saveButton.pack(padx=10)

        plt.ion()
        self.timer = []
        self.window.mainloop()

    def draw(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)
        self.line1, = self.ax.plot(0, 0, '.r') # Returns a tuple of line objects, thus the comma
        
        self.fig.canvas.draw()  # draw the initial plot
        self.fig.canvas.flush_events()
        self.timer = self.fig.canvas.new_timer(interval=UPDATE_RATE) # set up a timer to update the plot
        self.timer.add_callback(self.updatePlot)
        self.timer.start()
        
    def updatePlot(self):
        d=self.nano.getBuf()
        self.line1.set_xdata(np.linspace(0,len(d)/0.3,len(d)))
        self.line1.set_ydata(d)
        
        self.ax.relim()
        self.ax.autoscale_view()
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def stop(self):
        self.timer.stop()

        

        


if __name__ == "__main__":
    w = App()
