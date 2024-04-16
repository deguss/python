import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
import collections
import math
import datetime as dt
import pdb

import time, threading
CALLBACK_SECONDS = 1
BUFFERSIZE=10000
from serial.tools.list_ports import comports
import serial
import struct

# Define the fixed-size part of the struct format
FIXED_FORMAT_STR = '<HHbb'
#typedef struct {
#    uint16_t length;
#    uint16_t sps;
#    int8_t INP;
#    int8_t INM;
#    int32_t data[ADCBUFLEN];
#}
SIZE_FIXED_FORMAT = struct.calcsize(FIXED_FORMAT_STR)


#----------------------------------------------------------
class ADS1256(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, parent, boxes):
        tk.Frame.__init__(self, parent)   
        self.parent = parent
        self.boxes = boxes
        
        self.timeout=0
        self.tim=0
        self.resetBuf(BUFFERSIZE)
        self.length=0
        self.sps=0
        self.INP=0
        self.INM=0                        
        self.ofname='nr_data'
        self.ofhandle=None
        
        self.ports=[]
        for port in comports():
            self.ports.append(str(port))
        
        self.initUI()

    def initUI(self):
        # create GUI inside parent frame
        self.pack(fill=tk.BOTH, expand=1)
        
        boxname = tk.Label(self, text="ADS1256", font=("Arial", 16)) #title
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
        self.ser = serial.Serial(port=p, timeout=3)

        if (self.ser.is_open):
            self.msg(p+" opened")
            self.openButton.configure(state=tk.DISABLED)
            self.closeButton.configure(state=tk.NORMAL)
            self.lbox.configure(state=tk.DISABLED)
            
            self.ser.reset_input_buffer()
            
            self.timerCallBack()
            return True
        else:
            self.msg("Failed to open port "+p+"!")
            return False   


    def update_labels(self):
        self.boxes[0].config(text=str(self.INP))
        self.boxes[1].config(text=str(self.INM))
        self.boxes[2].config(text=str(self.sps)+"Hz")
        self.boxes[3].config(text=str(self.length))
        self.msg("Data of "+str(self.length)+" integers received")
        print("\n")
  
    def timerCallBack(self):
        if (self.ser.is_open):
            self.tim = threading.Timer(CALLBACK_SECONDS, self.timerCallBack)
            self.tim.start()

            try:
                if (self.ser.inWaiting() > 26):  #at 5Hz 5*32bit + fixed size part of the struct 
                    # Read the fixed-size part of the struct
                    fixed_data = self.ser.read(SIZE_FIXED_FORMAT)
                    if (len(fixed_data) == SIZE_FIXED_FORMAT):
                        
                        self.length, self.sps, self.INP, self.INM = struct.unpack(FIXED_FORMAT_STR, fixed_data)
                        self.update_labels()
                        
                        # Read the variable-length part of the struct (adc_data array)
                        adc_data_bytes = b''  # Initialize an empty byte buffer to accumulate data
                        bytes_needed = self.length * struct.calcsize('i')  # Calculate the total bytes needed for unpacking
                        print(str(bytes_needed)+"bytes expecting")
                        
                        # Loop to read data in parts until enough data is accumulated
                        while len(adc_data_bytes) < bytes_needed:
                            remaining_bytes = bytes_needed - len(adc_data_bytes)
                            adc_data_bytes += self.ser.read(remaining_bytes)
                            print(str(remaining_bytes)+"read")
                            rmnd=self.ser.inWaiting()
                            print(str(rmnd)+"remained in Rxbuf")
                            print(self.ser.read(rmnd))

                        if len(adc_data_bytes) == bytes_needed:
                            adc_data = struct.unpack('<{}i'.format(self.length), adc_data_bytes)
                            self.addSamples(adc_data)
                        else:
                            self.msg("Insufficient data to unpack")
                    else:
                        self.msg("Could not read sufficient data for header!")

            except ValueError as e:
                self.msg("ValueError! data corrupt! "+str(e))
                self.update_labels()

            except serial.SerialException as e:
                self.msg("Can not read serial port! "+str(e))
                self.serClose()

            except struct.error as e:
                self.msg("Can not unpack data! "+str(e))
                self.serClose()


        else:
            self.serClose()
            
            
    def saveButtonAction(self):
        if self.ofhandle == None:
            self.ofhandle = open(self.ofname+dt.datetime.strftime(dt.datetime.utcnow(),'%H%M')+'.txt','w')
            self.parent.saveButton.config(text='stop saving data')
        else:
            self.ofhandle.close()
            self.ofhandle = None
            self.parent.saveButton.config(text='start saving data')
        
    def addSamples(self, f):
        self.cbuf.append(f)
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
            print("\n"+mess+"\n")
        else:
            self.msgLabel.config(fg="green")

    def isSerOpen(self):
        try:
            if(self.ser.is_open):
                return True
            else:
                return False
        except:
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
        self.resetBuf(BUFFERSIZE)
        self.idx=0
        self.boxes[0].config(text="")
        self.boxes[1].config(text="")
        self.boxes[2].config(text="")
        self.boxes[3].config(text="")



UPDATE_RATE = 500
class App():
    def __init__(self):
        self.window = tk.Tk()
        self.window.geometry("900x350")
        self.window.title("Explore ADS1256")
        
        frame = tk.Frame(master=self.window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.boxes = []        
        for i in range(4):
            box = tk.Label(self.window, text="", font=("Arial", 16))
            box.pack(side=tk.LEFT, padx=10, pady=10)
            self.boxes.append(box)

        self.ads = ADS1256(frame, self.boxes)    
            
        startButton = tk.Button(self.window, text="start real-time view", command=self.draw)
        startButton.pack(side=tk.RIGHT, padx=10)

        stopButton = tk.Button(self.window, text="stop", command=self.stop)
        stopButton.pack(side=tk.RIGHT, padx=10)

        rstButton = tk.Button(self.window, text="reset view", command=self.rst)
        rstButton.pack(side=tk.RIGHT, padx=10)
        
        frame.saveButton = tk.Button(self.window, text="start saving data", command=self.ads.saveButtonAction)
        frame.saveButton.pack(side=tk.RIGHT, padx=10)

        plt.ion() #turn interactive plotting off
        
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
        text = self.boxes[2].cget("text")  # Get the text from box[1]
        sps = int(text.split("Hz")[0])
        
        d=self.ads.getBuf()        
        self.line1.set_xdata(np.linspace(0,1/sps*np.size(d),np.size(d)))
        self.line1.set_ydata(d)
        self.ax.relim()
        self.ax.autoscale_view()        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        
    def stop(self):
        self.timer.stop()


    def rst(self):
        self.ads.resetBuf(BUFFERSIZE)
        self.line1.set_xdata([])
        self.line1.set_ydata([])
 
        

        


if __name__ == "__main__":
    w = App()
