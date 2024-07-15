import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg)
import numpy as np
import tkinter as tk
from tkinter import ttk
import collections
import math
import datetime as dt
import pdb
import time, threading


BUFFERSIZE=50*60
from serial.tools.list_ports import comports
import serial
import struct


#----------------------------------------------------------
class USBserial(tk.Frame):
#----------------------------------------------------------
    def __init__(self, window, parent):
        self.parent = parent
        self.window = window
        tk.Frame.__init__(self, master=window, height=400, width=600, highlightbackground="gray", highlightthickness=1)
        
        self.timeout=0
        self.tim=0
        self.cnt=0
        self.length=0
        self.sps=0                    
        self.ofname='nr_data'
        self.ofhandle=None
        self.ports=[]
        self.initUI()
        self.scan()
        
    def scan(self):
        self.ports=[]
        self.portBox.delete(0, 'end')
        for port in comports():
            self.ports.append(str(port))
        self.portBox['values'] = self.ports
        self.portBox.current(0)


    def initUI(self):
        
        self.title = tk.Label(self, text="configuration", font=("Arial", 16)) #title
        self.title.grid(row=1, column=0, columnspan=5, sticky='nsew') # Add sticky='nsew' to make the frame fill the space

        self.comPorts = tk.StringVar(value=self.ports)
        self.portBox = ttk.Combobox(self, textvariable=self.comPorts, width=35)
        self.portBox.bind('<<ComboboxSelected>>', self.testSerPort) 
        self.portBox.grid(row=3, rowspan=3, column=0, columnspan=4, sticky='W', padx=10, pady=10)

        self.scanButton = tk.Button(self, text="scan", command=self.scan)
        self.scanButton.grid(row=2, column=0, sticky='W', padx=10, pady=0)
        
        self.openButton = tk.Button(self, text="open port", command=self.testSerPort)
        self.openButton.grid(row=3, column=2, sticky='E', padx=10, pady=5)
        
        self.closeButton = tk.Button(self, text="close port", command=self.serClose, state=tk.DISABLED)
        self.closeButton.grid(row=3, column=3, sticky='W', padx=10, pady=5)

        

        self.label1 = tk.Label(self, text="channels: ")
        self.label1.grid(row=6, column=0, sticky='E')
        self.channelbox = ttk.Combobox(self, state="disabled", values=["1", "2", "4"], width=2)
        self.channelbox.current(0)
        self.channelbox.bind('<<ComboboxSelected>>',self.update);
        self.channelbox.grid(row=6, column=1, sticky='W')

        self.label2 = tk.Label(self, text="time: ")
        self.label2.grid(row=6, column=2, sticky='E')
        self.l2 = tk.Label(self, text="    ", font=("Arial", 16))
        self.l2.grid(row=6, column=3, sticky='W')

        self.label3 = tk.Label(self, text="sample rate: ")
        self.label3.grid(row=7, column=0, sticky='E')
        self.spsbox = ttk.Combobox(self, state="disabled", values=["5Hz", "10Hz", "15Hz", "25Hz", "30Hz", "50Hz", "60Hz", "100Hz", "500Hz", "1kHz", "2kHz", "3.75kHz", "7.5kHz", "15kHz", "30kHz"], width=7)
        self.spsbox.current(0)
        self.spsbox.bind('<<ComboboxSelected>>',self.update);        
        self.spsbox.grid(row=7, column=1, sticky='W')
            
        self.label4 = tk.Label(self, text="received values: ")
        self.label4.grid(row=7, column=2, sticky='E')
        self.l4 = tk.Label(self, text="    ", font=("Arial", 16))
        self.l4.grid(row=7, column=3, sticky='W')


        self.check1var = tk.StringVar(value='1')
        self.check1Button = tk.Checkbutton(self, variable=self.check1var, text="record to internal SD-card", state=tk.DISABLED)
        self.check1Button.grid(row=8, columnspan=4, sticky='W', padx=10, pady=0)
        self.check2var = tk.StringVar(value='1')
        self.check2Button = tk.Checkbutton(self, variable=self.check2var, text="record to computer via USB", state=tk.DISABLED)
        self.check2Button.grid(row=9, columnspan=4, sticky='W', padx=10, pady=0)

        self.act1Button = tk.Button(self, text="start recording", command= lambda: self.update("start"), state=tk.DISABLED)
        self.act1Button.grid(row=14, column=0, sticky='E', padx=10, pady=5)
        self.act2Button = tk.Button(self, text="stop all recording", command= lambda: self.update("stop"), state=tk.DISABLED)
        self.act2Button.grid(row=14, column=1, sticky='E', padx=10, pady=5)

        self.msgLabel = tk.Label(self, text="")
        self.msgLabel.grid(row=15, column=0, columnspan=5, sticky='W')

    def update(self, e):
        if (e == "start" or e == "stop"): #set parameters and record
            print(f'#channel set to {self.channelbox.get()}, sps set to {self.spsbox.get()}')
            print(f'{self.check1var.get()} | {self.check2var.get()}')
        else: #set parameters only
            print(f'#channel set to {self.channelbox.get()}, sps set to {self.spsbox.get()}')


 
    def testSerPort(self, *args):      
        portSelected = self.comPorts.get()
        if (self.isSerOpen() == False): #if not yet open
            self.pr=portSelected.split()[0]                
            if(self.openSerial(self.pr) == False):
                self.msg(f'No data received. Right port {self.pr}?')


    def openSerial(self, p):
    # opens the serial port  p and listens to values sent by the instrument
        try:
            self.ser = serial.Serial(port=p, timeout=3)
        except serial.SerialException as e:
            self.msg(f'Could not open port! {e}')
            return False

        if (self.ser.is_open):
            self.msg(p+" opened")
            self.openButton.configure(state=tk.DISABLED)
            self.closeButton.configure(state=tk.NORMAL)
            self.portBox.configure(state=tk.DISABLED)
            self.channelbox.configure(state="readonly")
            self.spsbox.configure(state="readonly")
            self.check1Button.configure(state=tk.NORMAL)
            self.check2Button.configure(state=tk.NORMAL)
            self.act1Button.configure(state=tk.NORMAL)
            self.act2Button.configure(state=tk.NORMAL)

            pdb.set_trace()
            for child in self.window.frame.winfo_children():
                child.configure(state='disable')
            

            
            self.ser.reset_input_buffer()
            if (self.ser.inWaiting() > 0):
                self.ser.read(self.ser.inWaiting())
            self.resetBuf()
            
            self.timerCallBack()
            return True
        else:
            self.msg("Failed to open port "+p+"!")
            return False   

  
    def timerCallBack(self):
        if (self.ser.is_open):
            self.tim = threading.Timer(1, self.timerCallBack)
            self.tim.start()

            try:
                while (self.ser.inWaiting() > 52):  #at 5Hz 5*32bit + fixed size part of the struct 
                    # Read the fixed-size part of the struct
                    # Define the fixed-size part of the struct format
                    FIXED_FORMAT_STR = '<HHIHBB'
                    """
                        uint16_t length;
                        uint16_t sps;
                        uint32_t time;
                        uint16_t res16;
                        uint8_t  res8;
                        uint8_t channels;
                        int32_t data[ADCBUFLEN];
                    """
                    leng = struct.calcsize(FIXED_FORMAT_STR)                 
                    fixed_data = self.ser.read(leng)
                    if (len(fixed_data) == leng):
                        
                        self.length, self.sps, self.time, self.res16, self.res8, self.channels = struct.unpack(FIXED_FORMAT_STR, fixed_data)
                        self.updateStats()
                        
                        # Read the variable-length part of the struct (adc_data array)
                        bytes_needed = self.length * struct.calcsize('i')  # Calculate the total bytes needed for unpacking
                        
                        # Loop to read data in parts until enough data is accumulated
                        read = 0
                        if (self.ser.inWaiting() >= bytes_needed):
                            read+=bytes_needed
                            bin_data = self.ser.read(bytes_needed)
                            float_arr = np.frombuffer(bin_data, dtype=np.int32)
                            self.addSamples(float_arr / 2**23 * 5000) #mV
                            self.cnt+=1
                            #if (self.cnt <= 5):
                            #self.parent.updatePlot()
                        else:
                            self.msg("Insufficient data to unpack")
                        """
                        rmnd=self.ser.inWaiting()                            
                        if (rmnd==2):
                            self.ser.read(2)
                        rmnd=self.ser.inWaiting()                                
                        if (rmnd):
                            print(f'{rmnd} bytes remained in Rxbuf')
                            #print(self.ser.read(rmnd))
                        """
                            
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

    def resetBuf(self, bufferSize=BUFFERSIZE):
        self.cbuf=collections.deque(maxlen=int(bufferSize)) #reinit circ buffer
        self.idx=0
        self.cnt=0

    def getBuf(self):
        return np.array(list(self.cbuf))

    def updateStats(self):
            
        if (type(self.length) == int):
            self.l4.config(text=str(self.cnt)+"x"+str(self.length))
        else:
            self.l4.config(text="")
        
    def msg(self, mess):
        self.msgLabel.config(text=mess[:50])
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
        self.portBox.configure(state=tk.NORMAL)
        self.openButton.configure(state=tk.NORMAL)
        self.closeButton.configure(state=tk.DISABLED)
        self.channelbox.configure(state="disabled")
        self.spsbox.configure(state="disabled")
        self.check1Button.configure(state=tk.DISABLED)
        self.check2Button.configure(state=tk.DISABLED)
        self.act1Button.configure(state=tk.DISABLED)
        self.act2Button.configure(state=tk.DISABLED)        
        self.resetBuf()
        self.idx=0
        self.cnt=0
        self.sps=""
        self.length=""
        self.updateStats()
        self.scan()




UPDATE_RATE = 500
#----------------------------------------------------------
class Main(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, window):

        self.fig, self.ax = plt.subplots()
        self.u = USBserial(window, self)
        self.u.grid(row=0, column=0, padx=20, pady=20)
                
        self.frame = tk.Frame(master=window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        self.frame.grid(row=0, column=1, padx=20, pady=20)

        self.title = tk.Label(self.frame, text="Data", font=("Arial", 16)) #title
        self.title.grid(row=1, column=0, columnspan=5, sticky='nsew') # Add sticky='nsew' to make the frame fill the space
                  
        self.startButton = tk.Button(self.frame, text="real-time plot", command=self.initTimer)
        self.startButton.grid(row=2, column=0, padx=5, pady=5)

        self.stopButton = tk.Button(self.frame, text="waha")
        self.stopButton.grid(row=2, column=1, padx=5,  pady=5)

        self.rstButton = tk.Button(self.frame, text="clear buffer", command=self.clearBuf)
        self.rstButton.grid(row=2, column=2, padx=5,  pady=5)
            
        self.saveButton = tk.Button(self.frame, text="start saving data")
        self.saveButton.grid(row=2, column=3, padx=5,  pady=5)

        # Create Canvas
        canvas = FigureCanvasTkAgg(self.fig, master=self.frame)  
        canvas.get_tk_widget().grid(row=3, columnspan=5, sticky='nsew')
        self.line1, = self.ax.plot(0, 0, '.r') # Returns a tuple of line objects, thus the comma
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        for child in self.frame.winfo_children():
            child.configure(state='disable')

        #plt.ion() #turn interactive plotting off 
    
    def initTimer(self):
        self.timer = self.fig.canvas.new_timer(interval=UPDATE_RATE) # set up a timer to update the plot time in ms
        self.timer.add_callback(self.updatePlot)
        self.timer.start()
        self.startButton.configure(text="stop", command=self.stopTimer)

    def stopTimer(self):
        self.timer.stop()
        
            
    def updatePlot(self):
        if (self.fig == None):
            return
        
        try:
            self.sps = float(self.u.sps)
        except (ValueError) as e:
            print(e)
            self.timer.stop()
            plt.close()
            return
        
        d=self.u.cbuf
        self.line1.set_xdata(np.linspace(0,1/self.sps*np.size(d),np.size(d)))
        self.line1.set_ydata(d)
        self.ax.relim()
        self.ax.autoscale_view()        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        #print('|', end="")
        #print(f'sh={np.shape(self.u.cbuf)} avg = {np.mean(d)}')
        



    def clearBuf(self):
        self.u.resetBuf()
        self.line1.set_xdata([])
        self.line1.set_ydata([])
    
       


if __name__ == "__main__":
    window = tk.Tk()
    window.title("Explore ADS1256")
    app = Main(window)
       
    window.mainloop()





