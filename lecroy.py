import pdb
import numpy as np
import re
import atexit
import tkinter as tk
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import threading
import time
import pyvisa
from datetime import datetime
from functools import lru_cache

#----------------------------------------------------------
class Lecroy(tk.Frame):
#----------------------------------------------------------

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)   
        self.parent = parent        
        self.scope = 0
        self.ip = "192.168.1.12"

        self.ch1=[]
        self.ch2=[]
        self.dt=0
        self.tim=None

        atexit.register(self.closeDev)

        self.initUI()

    def initUI(self):
        # create GUI inside parent frame
        self.pack(fill=tk.BOTH, expand=1)
        
        self.name = tk.Label(self, text="Lecroy oscilloscope", font=("Arial", 16)) #title
        self.name.pack(padx=10, pady=10)

        self.ipbox = tk.Entry(self) #default ip
        self.ipbox.pack(padx=10, pady=10)
        self.ipbox.insert(0, self.ip)
        

        self.openButton = tk.Button(self, text="open resource", command=self.openDev)
        self.openButton.pack(padx=10, anchor=tk.E)

        self.closeButton = tk.Button(self, text="close resource", command=self.closeDev, state=tk.DISABLED) 
        self.closeButton.pack(padx=10, anchor=tk.E)

        self.getWFButton = tk.Button(self, text="capture and plot", command=self.plotWF, state=tk.DISABLED)
        self.getWFButton.pack(padx=10, anchor=tk.E)

        self.autoScaleC1 = tk.Button(self, text="autoscale C1", command=lambda: self.manualVertical(ch="C1"), state=tk.DISABLED)
        self.autoScaleC1.pack(padx=10, anchor=tk.E)

        self.autoScaleC2 = tk.Button(self, text="autoscale C2", command=lambda: self.manualVertical(ch="C2"), state=tk.DISABLED)
        self.autoScaleC2.pack(padx=10, anchor=tk.E)

        self.msgLabel = tk.Label(self, text="")
        self.msgLabel.pack(padx=10, anchor=tk.W)


        self.msgLabel = tk.Label(self, text="SCPI:")
        self.msgLabel.pack()
        self.inpBox = tk.Entry(self, width=20, state=tk.DISABLED, font=("Arial", 11))
        self.inpBox.pack()
        self.inpBox.bind('<Return>', self.onScpiEnter)

        # Start pyvisa 
        self.rm = pyvisa.ResourceManager('@py')

       
 
    def openDev(self):
        if (self.isDevOpen() == False): #if not yet open
            ip = self.ipbox.get()
            try:
                self.scope = self.rm.open_resource("VICP::"+ip+"::INSTR", timeout=5000)
            except Exception as e:
                self.msg("could not connect on "+ip+" !")
                print(e)
                self.rm.close()
                return

            try:
                idn = self.scope.query("*IDN?")
                print("idn="+idn)
                self.scope.write("MSG '"+__file__+"'")
                self.scope.write("COMM_HEADER OFF")
            except Exception as e:
                self.msg("communication error!")
                print(e)
                return
                
        if (self.isDevOpen() == True):
            dg = idn.split(',')

            if ("LECROY" in dg[0]):
                self.msg("connected to "+dg[0]+" "+dg[1])
                self.openButton.configure(state=tk.DISABLED)
                self.closeButton.configure(state=tk.NORMAL)
                self.getWFButton.configure(state=tk.NORMAL)
                self.autoScaleC1.configure(state=tk.NORMAL)
                self.autoScaleC2.configure(state=tk.NORMAL)
                self.ipbox.configure(state=tk.DISABLED)
                self.inpBox.configure(state=tk.NORMAL)
                self.inpBox.delete(0, tk.END)
                self.inpBox.insert(0,"*IDN?")
                self.inpBox.focus()  

            else:
                self.msg("Failed to connect to Lecroy!")
                self.closeDev()

    def getInt(self,string):
        import re
        match = re.search(r"\d+", string)

        if match:
            return int(match.group())
        else:
            raise ValueError("No numberical value found in the string: "+string)

    def getFloat(self,string):
        import re
        match = re.search(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", string)

        if match:
            return float(match.group())
        else:
            raise ValueError("No numberical value found in the string: "+string)

    def get_param_value(self,channel, parameter):
        s = self.scope.query(channel+":PAVA? "+parameter)
        print("param value: "+s)
        # "MAX,3.211,OK\n"
        elem = s.split(',')
        resp = elem[2].rstrip('\n')
        if (resp == 'OK' or resp == 'AV'): #for some parameters OK is reported, for others "Averaged over several periodes"
            return self.getFloat(elem[1])
        else:
            return resp

    def get_wavedesc_value(self,channel, parameter):
        s = self.scope.query(channel+":INSP? '"+parameter+"'")
        # "VERTICAL_GAIN      : 2.4414e-05"
        try:
            return self.getFloat(s)
        except: 
            print("response to query: "+s)
            raise ValueError("could not read "+parameter)
        

    def getVpp(self, ch="C1"):
        self.scope.write("STOP")
        c_max = self.get_param_value(ch, "MAX")
        c_min = self.get_param_value(ch, "MIN")
        if (type(c_max) == str or type(c_min) == str):
            print("OVERFLOW "+ch+"! min="+str(c_min)+" max="+str(c_max))
            self.msg("OVERFLOW!")
            self.scope.write("TRIG_MODE AUTO")
            return np.NaN
        else:
            c_pp=c_max-c_min
            print("Vpp("+ch+")    = "+str(c_pp))
            self.scope.write("TRIG_MODE AUTO")
            return c_pp

    def getDiffVpp(self):
        c1_pp = self.getVpp("C1")
        c2_pp = self.getVpp("C2")
        av = 20*np.log10(c2_pp / c1_pp)
        print(str(round(av,2))+"dB")
        self.msg(str(round(av,2))+"dB")
        return av
        

    def getSingleWF(self, ch="C1"):
        arr = self.scope.query_binary_values(ch+":WF? DAT1", datatype='h', container=np.array, is_big_endian=True)
        return arr

    def getWF(self):
        try:
            if (self.scope.query("C1:TRACE?").rstrip('\n') == 'ON' and self.scope.query("C2:TRACE?").rstrip('\n') == 'ON'):
                self.scope.write("STOP")
                self.ch1 = self.getSingleWF("C1")
                self.ch2 = self.getSingleWF("C2")
                self.scope.write("TRIG_MODE AUTO")
            else:
                self.msg("Turn on CH1 and CH2!")
                return False
                 
        except Exception as e:
            self.closeDev()
            self.msg("could not transfer waveform!")
            print("could not transfer waveform!")
            print(e)
            return False

        try:
            offs = self.get_wavedesc_value("C1", "VERTICAL_OFFSET")    
            gain = self.get_wavedesc_value("C1", "VERTICAL_GAIN")
            self.ch1 = gain * self.ch1 - offs

            offs = self.get_wavedesc_value("C2", "VERTICAL_OFFSET")    
            gain = self.get_wavedesc_value("C2", "VERTICAL_GAIN")
            self.ch2 = gain * self.ch2 - offs

                
            c_size = int(self.get_wavedesc_value("C1", "WAVE_ARRAY_COUNT"))
            self.dt = self.get_wavedesc_value("C1", "HORIZ_INTERVAL")
            #t_offs = self.get_wavedesc_value("C1", "HORIZ_OFFSET")
            #self.t = np.linspace(0-t_offs, (c_size*dt)-t_offs, c_size)
            return True
            
        except Exception as e:
            print(e)
            self.closeDev()
            
        

    def calcSpectrum(self):        
        M = len(self.ch1)
        window = np.hanning(M)

        fu = np.fft.rfft(self.ch1*window);
        fy = np.fft.rfft(self.ch2*window);

        fs=round(1/self.dt)
        self.dt = 1/fs
        faxis = np.fft.rfftfreq(M, self.dt)
        
        print("out of "+str(M)+" samples sampled at "+str(fs)+"Hz the Nyquist frq = "+str(round(max(faxis),3))+"Hz")
        
        # Find the frequency of the maximum magnitude in the FFT
        idx_m = np.argmax(np.abs(fu))
        fm = faxis[idx_m]
        print("Maximum energy at fm="+str(round(fm,3))+"Hz")
        print("ch1(fm) = "+str(round(20*np.log10(np.abs(fu[idx_m]))))+"dB, ch2(fm) = "+str(round(20*np.log10(np.abs(fy[idx_m]))))+"dB")
        att = 20*np.log10(np.abs(fu[idx_m]) / np.abs(fy[idx_m]))
        print("attenuation = "+str(round(att,2))+"dB")

        return (faxis, fu, fy)



    def plotWF(self, f_exc=None):
        self.getWF()
        (faxis, fu, fy) = self.calcSpectrum()

        fig, axs = plt.subplots(nrows=2, ncols=2, squeeze=False, sharex='col', figsize=(10,8))
        fm=plt.get_current_fig_manager()
        fm.window.wm_geometry('1200x1000+0+0') #place the window on top left corner of screen
        if (f_exc is not None):
            fm.window.title("Analysis at "+str(f_exc)+"Hz") 

        plt.ion() #disp fig without blocking
        M = len(self.ch1)
        t = np.linspace(0, M*self.dt, M)
        axs[0][0].plot(t, self.ch1, color='gold')
        axs[1][0].plot(t, self.ch2, color='maroon')
        
        formatter = ticker.EngFormatter()    # Set the y-axis formatter to display values in ms, us, ns, or ps
        axs[1][0].xaxis.set_major_formatter(formatter) # Apply the formatter to the y-axis

        axs[0][0].set_title("Time-domain signals")
        axs[0][0].set(ylabel='input amplitude (V)')
        axs[0][0].grid()
        axs[1][0].set(xlabel='time (s)', ylabel='output amplitude (V)')
        axs[1][0].grid()
        plt.xlim(min(t), max(t))


        axs[0][1].semilogx(faxis, 20*np.log10(np.abs(fu) / np.max(np.abs(fu)) ), '.')
        axs[1][1].semilogx(faxis, 20*np.log10(np.abs(fy) / np.max(np.abs(fu)) ), '.')

        

        axs[0][1].set_title("Frequency-response analysis")
        axs[0][1].set(ylabel='FFT(input) normalized')
        axs[0][1].grid()
        axs[1][1].set(xlabel='frequency (Hz)', ylabel='FFT(output) dBV')        
        axs[1][1].grid()
        plt.xlim(faxis[1], max(faxis)/10)
              

        plt.show(block=False)  # Show plot in a non-blocking way
        return (faxis, fu, fy)


    def setTimeBase(self, tbase):
        self.scope.write("TDIV "+str(tbase/10))
        
    def getTimeBase(self):
        return float(self.scope.query("TDIV?"))*10
    
    def setVertical(self, ch="C1", vscreen=1):
        self.scope.write(ch+":VDIV "+str(vscreen/8))

    def getVertical(self, ch="C2"):
        return float(self.scope.query(ch+":VDIV?"))*8
        
    def autoVertical(self, ch="C2"):
        self.scope.write(ch+":AUTO_SETUP FIND")
        
    def manualVertical(self, ch=None):
        if (len(self.ch1) == 0):
            self.getWF()
        if (ch == "C1" or ch is None):
            c1_pp = np.ptp(self.ch1)
            self.manualVerticalEach(c1_pp, "C1")
        if (ch == "C2" or ch is None):
            c2_pp = np.ptp(self.ch2)
            self.manualVerticalEach(c2_pp, "C2")
        
    def manualVerticalEach(self, vpp, ch):        
        screen_v = self.getVertical(ch)
        waittime = max(self.getTimeBase()*0.1,1)
        m = vpp/screen_v

        if (m > 0.99):                 # -> fast range down
            self.msg("ranging down "+ch+" ("+str(round(m,3))+")")
            self.setVertical(ch, screen_v*8)
        elif (m > 0.9 and m < 0.99):   # -> range down
            self.msg("ranging down "+ch+" ("+str(round(m,3))+")")
            self.setVertical(ch, screen_v*2)
        elif (vpp == 0):               #no signal in the screen
            self.msg("ranging in progress "+ch+"... set default")
            self.setVertical(ch, 8.0)  # -> 1V/DIV
        elif (m < 0.1):                # very small signal -> turn VDIV up
            self.msg("ranging up "+ch+" ("+str(round(m,3))+")")
            self.setVertical(ch, screen_v*1.2*m)
        elif (m < 0.3):
            self.msg("ranging up "+ch+" ("+str(round(m,3))+")")
            self.setVertical(ch, screen_v/2)
        else:
            self.msg("autoranging "+ch+" done (m="+str(round(m,3))+", 8*VDIV="+str(screen_v)+")")

        
    def clearSweeps(self):
        self.scope.write("CLEAR_SWEEPS")
    

    def onScpiEnter(self, *args):
        m=self.inpBox.get()
        self.scpi_send(m)
        self.inpBox.delete(0, tk.END)
        
    def scpi_send(self, m):
        try:
            if ('?' in m):
                print(self.scope.query(m))
            else:
                self.scope.write(m)
                print()

            r = int(self.scope.query("CMR?"))
            if (r > 0):
                if (r == 1):
                    print("unrecognized command")
                elif(r == 2):
                    print("illegal header path")
                elif(r==3):
                    print("illegal number")
                elif(r==4):
                    print("illegal number suffix")
                elif(r==5):
                    print("unrecognized keyword")
                elif(r==6):
                    print("string error")
                else:
                    print("other error")                                   
        except:
            print("command error / no response!")
            print(self.scope.query("CHL?"))
            
    def resetBuf(self):
        self.ch1=[]
        self.ch2=[]
        
        
    def msg(self, mess):
        current_time_str = datetime.now().strftime("%H:%M:%S.%f")
        print(current_time_str + " \t"+mess)
        self.msgLabel.config(text=mess)
        if '?' in mess or '!' in mess:
            self.msgLabel.config(fg="red")
        else:
            self.msgLabel.config(fg="green")

    def isDevOpen(self):
        if (self.scope):
            return True
        else:
            return False        


    def closeDev(self):
        if (self.isDevOpen()):
            self.scope.close()

        self.rm.close()

        self.msg("resource closed")
        print("resource closed")
        self.openButton.configure(state=tk.NORMAL)
        self.closeButton.configure(state=tk.DISABLED)
        self.getWFButton.configure(state=tk.DISABLED)
        self.autoScaleC1.configure(state=tk.DISABLED)
        self.autoScaleC2.configure(state=tk.DISABLED)        
        self.ipbox.configure(state=tk.NORMAL)
        self.inpBox.configure(state=tk.DISABLED)
        


        
class App():
    def __init__(self):
        self.window = tk.Tk()
        self.window.geometry("700x400")
        self.window.title("Frequency response analysis")
        
        self.frame = tk.Frame(master=self.window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        self.frame.pack(side=tk.LEFT, padx=10, pady=10)
        self.lecroy = Lecroy(self.frame)

        self.window.protocol("WM_DELETE_WINDOW", self.close)
        #self.window.attributes('-alpha',0.8)
        
        self.window.mainloop()        

    def close(self):
        self.lecroy.closeDev()
        print("exitting")
        self.window.destroy()

        
if __name__ == "__main__":
    w = App()





"""
When you compute the Fast Fourier Transform (FFT) of a time-domain signal in volts and plot the FFT using semilogx, the units of the FFT values plotted on the y-axis depend on how you process and scale the FFT result.

FFT Magnitude Plot (normalized):
If you plot the magnitude of the FFT directly without any scaling or normalization, the y-axis would represent the magnitude of the frequency components in volts. However, the absolute magnitude values might be difficult to interpret directly due to the scaling factors involved in the FFT computation.

FFT Power Spectrum (V^2/Hz):
Often, when dealing with power spectral density or power spectrum plots, the FFT result is squared to obtain power values. In this case, the y-axis represents power values in volts squared per Hertz (V^2/Hz). This can be achieved by calculating np.abs(fft_result)**2.
In this scenario, if you plot the power spectrum using semilogx, the y-axis would represent the power values in volts squared per Hertz (V^2/Hz) on a logarithmic scale.

FFT Magnitude Spectrum (V/Hz or dB/Hz):
To interpret the FFT magnitude in terms of amplitude spectral density, you can either directly use np.abs(fft_result) or convert the squared power values back to magnitude by taking the square root. This results in units of volts per Hertz (V/Hz).
Alternatively, you can plot the magnitude in decibels (dB) by converting the magnitude to dB using 20 * np.log10(np.abs(fft_result)) which would be in dB/Hz.
Depending on the specific application and analysis, you may choose to represent the FFT plot in terms of magnitude, power, amplitude spectral density, or in decibels. The choice of representation will determine the units and scale of the FFT values when plotted using semilogx.
"""


