import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
import collections
import math
import datetime as dt
import pdb
import time, threading


BUFFERSIZE=30000*60*5
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
    def __init__(self, window, parent):
        self.parent = parent
        tk.Frame.__init__(self, master=window, height=400, width=600, highlightbackground="gray", highlightthickness=1)
        
        self.timeout=0
        self.tim=0
        self.cnt=0
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
                    fixed_data = self.ser.read(SIZE_FIXED_FORMAT)
                    if (len(fixed_data) == SIZE_FIXED_FORMAT):
                        
                        self.length, self.sps, self.INP, self.INM = struct.unpack(FIXED_FORMAT_STR, fixed_data)
                        self.updateStats()
                        
                        # Read the variable-length part of the struct (adc_data array)
                        bytes_needed = self.length * struct.calcsize('i')  # Calculate the total bytes needed for unpacking
                        
                        # Loop to read data in parts until enough data is accumulated
                        read = 0
                        if (self.ser.inWaiting() >= bytes_needed):
                            read+=bytes_needed
                            bin_data = self.ser.read(bytes_needed)
                            int_data = struct.unpack('<{}i'.format(self.length), bin_data)
                            self.cbuf.append(int_data)
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
        self.l1.config(text=str(self.INP))
        
        if (self.INM == -1):
            self.l2.config(text="GND")
        else:
            self.l2.config(text=str(self.INM))
            
        if (type(self.sps) == str):
            self.l3.config(text="")
        else:
            self.l3.config(text=str(self.sps)+"Hz")
            
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
        self.lbox.configure(state=tk.NORMAL)
        self.openButton.configure(state=tk.NORMAL)
        self.closeButton.configure(state=tk.DISABLED)
        self.resetBuf()
        self.idx=0
        self.cnt=0
        self.INP=""
        self.INM=""
        self.sps=""
        self.length=""
        self.updateStats()




UPDATE_RATE = 500
#----------------------------------------------------------
class Main(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, window):

        self.fig = None
        self.u = USBserial(window, self)
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
        print(f'sh={np.shape(self.u.cbuf)} avg = {np.mean(d)}')
        
    def stop(self):
        self.timer.stop()


    def clearBuf(self):
        self.u.resetBuf()
        self.line1.set_xdata([])
        self.line1.set_ydata([])
    
       


if __name__ == "__main__":
    window = tk.Tk()
    window.title("Explore ADS1256")
    app = Main(window)
       
    window.mainloop()





