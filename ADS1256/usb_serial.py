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
class USBserial(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, parent):
        super().__init__()
        tk.Frame.__init__(self, parent, height=400, width=600, highlightbackground="gray", highlightthickness=1)
        
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
        
        self.title = tk.Label(self, text="ADS1256", font=("Arial", 16)) #title
        self.title.grid(row=1, column=0, columnspan=5, sticky='nsew') # Add sticky='nsew' to make the frame fill the space

        self.choicesvar = tk.StringVar(value=self.ports)
        self.lbox = tk.Listbox(self, listvariable=self.choicesvar, width=35, height=6, activestyle='none', font=("Courier", 10))
        self.lbox.bind("<Double-1>", self.testSerPort) #register doubleclick action
        self.lbox.grid(row=2, rowspan=4, column=0, columnspan=4, sticky='W', padx=10, pady=10)

        self.openButton = tk.Button(self, text="open port", command=self.testSerPort)
        self.openButton.grid(row=2, column=4, sticky='E', padx=10, pady=5)
        
        self.closeButton = tk.Button(self, text="close port", command=self.serClose, state=tk.DISABLED)
        self.closeButton.grid(row=3, column=4, sticky='E', padx=10, pady=5)

        self.label1 = tk.Label(self, text="input: ")
        self.label1.grid(row=6, column=0, sticky='E')
        self.l1 = tk.Label(self, text="    ", font=("Arial", 16))
        self.l1.grid(row=6, column=1, sticky='W')

        self.label2 = tk.Label(self, text="ref: ")
        self.label2.grid(row=6, column=2, sticky='E')
        self.l2 = tk.Label(self, text="    ", font=("Arial", 16))
        self.l2.grid(row=6, column=3, sticky='W')

        self.label3 = tk.Label(self, text="sample rate: ")
        self.label3.grid(row=7, column=0, sticky='E')
        self.l3 = tk.Label(self, text="      ", font=("Arial", 16))
        self.l3.grid(row=7, column=1, sticky='W')
            
        self.label4 = tk.Label(self, text="received values: ")
        self.label4.grid(row=7, column=2, sticky='E')
        self.l4 = tk.Label(self, text="    ", font=("Arial", 16))
        self.l4.grid(row=7, column=3, sticky='W')
        

        self.msgLabel = tk.Label(self, text="")
        self.msgLabel.grid(row=9, column=0, columnspan=5, sticky='W')


 
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
            if (self.ser.inWaiting() > 0):
                self.ser.read(self.ser.inWaiting())
            self.resetBuf(BUFFERSIZE)
            
            self.timerCallBack()
            return True
        else:
            self.msg("Failed to open port "+p+"!")
            return False   

  
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
                        self.updateStats()
                        
                        # Read the variable-length part of the struct (adc_data array)
                        adc_data_bytes = b''  # Initialize an empty byte buffer to accumulate data
                        bytes_needed = self.length * struct.calcsize('i')  # Calculate the total bytes needed for unpacking
                        
                        # Loop to read data in parts until enough data is accumulated
                        while len(adc_data_bytes) < bytes_needed:
                            remaining_bytes = bytes_needed - len(adc_data_bytes)
                            adc_data_bytes += self.ser.read(remaining_bytes)
                            rmnd=self.ser.inWaiting()
                            if (rmnd==2):
                                self.ser.read(2)
                            rmnd=self.ser.inWaiting()                                
                            if (rmnd):
                                print(f'{bytes_needed} bytes expecting, {remaining_bytes} read, {rmnd} remained in Rxbuf')
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
                self.updateStats()

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

    def updateStats(self):
        self.l1.config(text=str(self.INP))
        if (self.INM == -1):
            self.l2.config(text="GND")
        else:
            self.l2.config(text=str(self.INM))
        if (self.sps == ""):
            self.l3.config(text="")
        else:
            self.l3.config(text=str(self.sps)+"Hz")
        self.l4.config(text=str(self.length))    
        
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
        self.INP=""
        self.INM=""
        self.sps=""
        self.length=""
        self.updateStats()

# ---------- END ----- USBserial -----------------


UPDATE_RATE = 500
class Main(tk.Frame):
    def __init__(self, window):
        
        self.u = USBserial(window)
        self.u.grid(row=0, column=0, padx=20, pady=20)
                
        self.frame = tk.Frame(master=window, height=250, width=250)
        self.frame.grid(row=0, column=1, padx=20, pady=20)
                  
        self.startButton = tk.Button(self.frame, text="start real-time view", command=self.draw)
        self.startButton.grid(row=0, pady=5)

        self.stopButton = tk.Button(self.frame, text="stop real-time view", command=self.stop)
        self.stopButton.grid(row=1, pady=5)

        self.rstButton = tk.Button(self.frame, text="clear buffer", command=self.clearBuf)
        self.rstButton.grid(row=2, pady=5)
            
        self.saveButton = tk.Button(self.frame, text="start saving data")
        self.saveButton.grid(row=3, pady=5)

        plt.ion() #turn interactive plotting off 
    
    def draw(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot()
        self.line1, = self.ax.plot(0, 0, '.r') # Returns a tuple of line objects, thus the comma
        
        self.fig.canvas.draw()  # draw the initial plot
        self.fig.canvas.flush_events()
        self.timer = self.fig.canvas.new_timer(interval=UPDATE_RATE) # set up a timer to update the plot time in ms
        self.timer.add_callback(self.updatePlot)
        self.timer.start()     

        
            
    def updatePlot(self):
        try:
            self.sps = float(self.u.sps)
        except (ValueError) as e:
            print(e)
            self.timer.stop()
            self.fig.close()
            return
        
        d=self.u.cbuf
        self.line1.set_xdata(np.linspace(0,1/self.sps*np.size(d),np.size(d)))
        self.line1.set_ydata(d)
        self.ax.relim()
        self.ax.autoscale_view()        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        print('|', end="")
        
    def stop(self):
        self.timer.stop()


    def clearBuf(self):
        self.u.serClose()
        self.line1.set_xdata([])
        self.line1.set_ydata([])
    
       


if __name__ == "__main__":
    window = tk.Tk()
    window.title("Explore ADS1256")
    app = Main(window)
       
    window.mainloop()





