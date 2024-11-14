import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
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
from tkinter import messagebox
import serial.tools.list_ports

#----------------------------------------------------------
class USBserial(tk.Frame):
#----------------------------------------------------------
    def __init__(self, window):
        self.window = window
                
        self.timeout=0
        self.tim=0
        self.cnt=0
        self.length=0
        self.sps=0                    
        self.ofname='nr_data'
        self.ofhandle=None
        self.ports=[]


        menubar = tk.Menu(self.window)
        self.window.config(menu=menubar)

        # Create a "Connect" Menu
        connect_menu = tk.Menu(menubar,  tearoff=0)
        menubar.add_cascade(label="Connect", menu=connect_menu)

        self.port = tk.StringVar()
        for s in self.serial_ports():
            connect_menu.add_radiobutton(label=s, variable=self.port, command=lambda s=s: self.openSerial(s))
        connect_menu.add_separator()
        connect_menu.add_command(label="close ports", command=self.serClose)

        # Create a "Help" Menu
        help_menu = tk.Menu(menubar,  tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        

    def initUI(self):
        self.frequency_map = {
            2: "2.5Hz",
            5: "5Hz",
            10: "10Hz",
            15: "15Hz",
            25: "25Hz",
            30: "30Hz",
            50: "50Hz",
            60: "60Hz",
            100: "100Hz",
            500: "500Hz",
            1000: "1kHz",
            2000: "2kHz",
            3750: "3.75kHz",
            7500: "7.5kHz",
            15000: "15kHz",
            30000: "30kHz",
        }        
        self.frame = tk.Frame(master=window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        self.frame.grid(row=0, column=0, padx=10, pady=10, sticky='new')
        self.frame.grid_propagate(0)  
        
        self.title = tk.Label(self.frame, text="configuration", font=("Arial", 16)) #title
        self.title.grid(row=1, column=0, columnspan=5, sticky='nsew') # Add sticky='nsew' to make the frame fill the space

        self.label2 = tk.Label(self.frame, text="time: ")
        self.label2.grid(row=6, column=0, sticky='E')
        self.l2 = tk.Label(self.frame, text="    ", font=("Arial", 16))
        self.l2.grid(row=6, column=1, sticky='W')

        self.label1 = tk.Label(self.frame, text="channels: ")
        self.label1.grid(row=6, column=0, sticky='E')
        self.channelbox = ttk.Combobox(self.frame, values=["1", "2", "4"], width=2)
        self.channelbox.current(0)
        #self.channelbox.bind('<<ComboboxSelected>>',self.update);
        self.channelbox.grid(row=6, column=1, sticky='W')

        self.label3 = tk.Label(self.frame, text="sample rate: ")
        self.label3.grid(row=7, column=0, sticky='E')
        self.spsbox = ttk.Combobox(self.frame, values=list(self.frequency_map.values()), width=7)
        self.spsbox.current(2)
        self.spsbox.grid(row=7, column=1, sticky='W')            

        self.check1var = tk.StringVar(value='1')
        self.check1Button = tk.Checkbutton(self.frame, variable=self.check1var, text="record to internal SD-card")
        self.check1Button.grid(row=8, columnspan=2, sticky='W', padx=10, pady=0)
        self.check2var = tk.StringVar(value='1')
        self.check2Button = tk.Checkbutton(self.frame, variable=self.check2var, text="record to computer via USB")
        self.check2Button.grid(row=9, columnspan=2, sticky='W', padx=10, pady=0)

        self.label3 = tk.Label(self.frame, text="settings")
        self.label3.grid(row=11, column=0, sticky='E')
        self.act3Button = tk.Button(self.frame, text="get", command= lambda: self.update("get"))
        self.act3Button.grid(row=11, column=1, sticky='W', padx=10, pady=5)
        self.act4Button = tk.Button(self.frame, text="set", command= lambda: self.update("set"))
        self.act4Button.grid(row=11, column=1, sticky='N', padx=10, pady=5)
        self.act5Button = tk.Button(self.frame, text="*RST", command= lambda: self.command_ADS("*RST"))
        self.act5Button.grid(row=11, column=1, sticky='E', padx=10, pady=5)        

        self.label4 = tk.Label(self.frame, text="received values: ")
        self.label4.grid(row=10, column=0, sticky='E')
        self.l4 = tk.Label(self.frame, text="    ", font=("Arial", 12))
        self.l4.grid(row=10, column=1, sticky='W')

        self.act1Button = tk.Button(self.frame, text="start recording", command= lambda: self.update("start"), state=tk.DISABLED)
        self.act1Button.grid(row=14, column=0, sticky='E', padx=10, pady=5)
        self.act2Button = tk.Button(self.frame, text="stop all recording", command= lambda: self.update("stop"))
        self.act2Button.grid(row=14, column=1, sticky='E', padx=10, pady=5)

        self.msgLabel = tk.Label(self.frame, text="")
        self.msgLabel.grid(row=15, column=0, columnspan=5, sticky='W')

    def deinitUI(self):
        self.frame.destroy()

    def serial_ports(self):    
        return serial.tools.list_ports.comports()

    def command_ADS(self, cmd):
        self.msg(cmd)
        self.ser.write(cmd.encode('utf-8'))

    def query_ADS(self, cmd):
        if (self.ser.inWaiting() > 0):  #discary anything in the RxBuffer
            self.ser.read(self.ser.inWaiting())
        self.command_ADS(cmd)
        time.sleep(0.1)
        if (self.ser.inWaiting() > 5):
            return self.ser.read(self.ser.inWaiting())
        return 0
            

        
    def update(self, e):
        if (e == "get"):
            #self.chan = self.query_ADS("CONF:CHAN?")
            self.sps = int(self.query_ADS("CONF:SPSI?"))
            print(f'sample rate {self.sps} determined.')
                # Set the combobox if there's a matching value
            if self.sps in self.frequency_map:
                self.spsbox.set(self.frequency_map[self.sps])            
            
        elif (e == "set"):
            pass
            
        if (e == "start"):
            self.command_ADS("INIT:ELOG")
            self.command_ADS("INIT:DLOG")
            self.act1Button.config(state=tk.DISABLED)
            self.window.data.initUI()
            
        elif (e == "stop"):
            self.command_ADS("ABOR:ELOG")
            self.command_ADS("ABOR:DLOG")
            self.act1Button.config(state=tk.NORMAL)
            self.window.data.stopTimer()
            self.window.data.deinitUI()
            self.resetBuf()
        

        else:

            self.command_ADS(f'CONF:CHAN {self.channelbox.get()}')
            
            #self.command_ADS(f'CONF:SPS {self.spsbox.get()}')
            
            selected_value = self.spsbox.get()            
            index = self.spsbox['values'].index(selected_value)  # Find the index of the selected value
            self.command_ADS(f'CONF:SPSI {index}')
            
            
            
        



    def openSerial(self, p):
        pr = str(p).split()[0]
        if (self.isSerOpen() == False): #if not yet open
            try:
                self.ser = serial.Serial(port=pr, timeout=3)
            except serial.SerialException as e:
                self.msg(f'Could not open port! {e}')
                return False

        if (self.ser.is_open):
            self.initUI()
            self.msg(pr+" opened")
            self.act1Button.config(state=tk.NORMAL)
            
            self.ser.reset_input_buffer()
            if (self.ser.inWaiting() > 0):
                self.ser.read(self.ser.inWaiting())
            self.resetBuf()
            
            self.timerCallBack()
            return True
        else:
            self.msg(f'Failed to open port {pr}!')
            return False   

  
    def timerCallBack(self):
        if (self.ser.is_open):
            self.l4.config(text=f'{self.ser.inWaiting()}')
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
            except:
                print("Something else went wrong")                


        else:
            self.msg("Port could not be opened!") 
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
            self.l4.config(text=f'{self.cnt}x{self.length}')
            self.act1Button.configure(state=tk.NORMAL)
            if (len(self.cbuf) == 0):
                print(f'sample rate {self.sps} determined.')
                # Set the combobox if there's a matching value
                if self.sps in self.frequency_map:
                    self.spsbox.set(self.frequency_map[self.sps])
                
        else:
            self.l4.config(text="")
        
    def msg(self, mess):
        if hasattr(self, 'msgLabel'):
            self.msgLabel.config(text=mess[:50])
            if '?' in mess or '!' in mess:
                self.msgLabel.config(fg="red")
            else:
                self.msgLabel.config(fg="green")
        else:
            print("\n"+mess+"\n")

    def isSerOpen(self):
        try:
            if(self.ser.is_open):
                return True
            else:
                return False
        except:
            return False
         


    def serClose(self):
        if (self.tim):
            if (self.tim.is_alive()):
                self.tim.cancel()
        if (self.isSerOpen()):
            self.ser.close()
        if (self.port.get() != ""):
            pr = self.port.get().split()[0]
            self.port.set("")
            print(f'{pr} closed')            
            
        self.msg("port closed")
        self.resetBuf()
        self.idx=0
        self.cnt=0
        self.sps=""
        self.length=""
        self.updateStats()
        
        self.deinitUI()
        self.window.data.deinitUI()


    def show_about(self):
        messagebox.showinfo("About", "precise data instruments\nVersion 1.0\n© 2024 Daniel Piri")



UPDATE_RATE = 500
#----------------------------------------------------------
class Data(tk.Frame):
#----------------------------------------------------------    
    def __init__(self, window):
        self.window = window

    def initUI(self):
        self.frame = tk.Frame(master=window, height=600, width=1200, highlightbackground="gray", highlightthickness=1)
        self.frame.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
        self.frame.grid_propagate(0)

        self.fig, self.ax = plt.subplots()
        
        self.label1 = tk.Label(self.frame, text="window length:")
        self.label1.grid(row=2, column=1, sticky='E')
        self.channelbox = ttk.Combobox(self.frame, values=["10s", "30s", "1min", "3min", "10min", "30min", "1h", "3h", "6h", "12h", "24h"], width=5)
        self.channelbox.current(0)
        self.channelbox.bind('<<ComboboxSelected>>',self.update);
        self.channelbox.grid(row=2, column=2, sticky='W')

        self.autoscaley = tk.StringVar(value='1')
        self.check1Button = tk.Checkbutton(self.frame, variable=self.autoscaley, text="autoscale y")
        self.check1Button.grid(row=2, column=3, padx=5, pady=5)
        

        self.rstButton = tk.Button(self.frame, text="reset", command=self.clearBuf)
        self.rstButton.grid(row=2, column=4, padx=5,  pady=5)
            
        self.saveButton = tk.Button(self.frame, text="start saving data")
        self.saveButton.grid(row=2, column=5, padx=5,  pady=5)


        
        # Create Canvas
        canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        
        canvas.get_tk_widget().grid(row=3, columnspan=8, sticky='nsew')
        canvas.get_tk_widget().grid_propagate(0) #prevents it from resizing when its contents change.
        self.line1, = self.ax.plot(0, 0, '.r') # Returns a tuple of line objects, thus the comma
        canvas.draw()

        # pack_toolbar=False will make it easier to use a layout manager later on.
        toolbar = NavigationToolbar2Tk(canvas, self.frame, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=2, column=4, ipadx=40, ipady=10, sticky='ew', padx=20)
        toolbar.grid_propagate(0)

        self.initTimer()

    def deinitUI(self):
        self.frame.destroy()


    def update(self, event):
        pass
    
    def initTimer(self):
        self.timer = self.fig.canvas.new_timer(interval=UPDATE_RATE) # set up a timer to update the plot time in ms
        self.timer.add_callback(self.updatePlot)
        self.timer.start()

    def stopTimer(self):
        self.timer.stop()
        
            
    def updatePlot(self):
        if (self.fig == None):
            return
        
        try:
            self.sps = float(self.window.usb.sps)
        except (ValueError) as e:
            print(e)
            self.timer.stop()
            return
        
        d=self.window.usb.cbuf
        self.line1.set_xdata(np.linspace(0,1/self.sps*np.size(d),np.size(d)))
        self.line1.set_ydata(d)
        self.ax.relim()
        self.ax.autoscale_view()        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def clearBuf(self):
        self.window.usb.resetBuf()
        self.line1.set_xdata([])
        self.line1.set_ydata([])
    
       


if __name__ == "__main__":
    window = tk.Tk()
    window.iconbitmap('ic.ico')
    window.title("precise data client")
    window.geometry("1500x650+0+0")

    window.usb = USBserial(window)
    window.data = Data(window)
       
    window.mainloop()

