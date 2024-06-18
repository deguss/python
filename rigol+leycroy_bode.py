import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import filedialog
import pdb
import atexit
import os
from datetime import datetime

from rigol import *
from lecroy import *


VOLT = 0.004



class Bode():
    def __init__(self):

        self.figBode = None

        self.window = tk.Tk()
        self.window.geometry("650x550")
        self.window.title("Frequency response analyzer")

                
        self.frame1 = tk.Frame(master=self.window, highlightbackground="gray", highlightthickness=1) # create the left frame
        self.frame1.grid(row=0, column=0, padx=10, pady=10, sticky='nsew') # Add sticky='nsew' to make the frame fill the space
        self.scope = Lecroy(self.frame1)   
        
        self.frame2 = tk.Frame(master=self.window, highlightbackground="gray", highlightthickness=1)
        self.frame2.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
        self.rigol = Rigol(self.frame2)

        self.bodeFrame = tk.Frame(master=self.window, highlightbackground="gray", highlightthickness=1)
        self.bodeFrame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky='nsew')
        self.bodeName = tk.Label(self.bodeFrame, text="Frequency analysis", font=("Arial", 16))
        self.bodeName.grid(row=0, column=0, columnspan=4, sticky='nsew')
        
        label = tk.Label(self.bodeFrame, text="start frequency (Hz)")
        label.grid(row=1, column=0, sticky='E')
        self.start_f = tk.Entry(self.bodeFrame, width=5)
        self.start_f.insert(0, "10")
        self.start_f.grid(row=1, column=1, sticky='W')
        
        label = tk.Label(self.bodeFrame, text="stop frequency (Hz)")
        label.grid(row=2, column=0, sticky='E')
        self.stop_f = tk.Entry(self.bodeFrame, width=5)
        self.stop_f.insert(0, "100.0")
        self.stop_f.grid(row=2, column=1, sticky='W')

        label = tk.Label(self.bodeFrame, text="steps")
        label.grid(row=3, column=0, sticky='E')
        self.steps = tk.Entry(self.bodeFrame, width=3)
        self.steps.insert(0, "31")
        self.steps.grid(row=3, column=1, sticky='W')

        #choicesvar = tk.StringVar(value=self.ports)
        #self.lbox = tk.Listbox(self.bodeFrame, listvariable=choicesvar, width=35, height=6, activestyle='none', font=("Courier", 10))
        #self.lbox.bind("<Double-1>", self.chooseDev) #register doubleclick action

        
        self.startButton = tk.Button(self.bodeFrame, text="start sweeping", command=self.initFrq)
        self.startButton.grid(row=1, column=3, padx=20, pady=1, sticky='E')
        self.cancelButton = tk.Button(self.bodeFrame, text="STOP", command=self.cancel)
        self.cancelButton.grid(row=2, column=3, padx=20, pady=1, sticky='E')
        self.loadFile = tk.Button(self.bodeFrame, text="load from file", command=self.loadFile)
        self.loadFile.grid(row=3, column=3)

        self.UIlinfrq = tk.IntVar()
        self.UIcheck0 = tk.Checkbutton(self.bodeFrame, text="linear frequency sweep", variable=self.UIlinfrq)
        self.UIcheck0.grid(row=4, columnspan=3, sticky='W')
        self.UIdisplayTimeFrq = tk.IntVar()
        self.UIcheck1 = tk.Checkbutton(self.bodeFrame, text="display time and frequency domain signals for each frequency", variable=self.UIdisplayTimeFrq)
        self.UIcheck1.grid(row=5, columnspan=3, sticky='W')
        self.UIdisplayEachBode = tk.IntVar()
        self.UIcheck2 = tk.Checkbutton(self.bodeFrame, text="display the bode-plot of each response on each excitation frequency", variable=self.UIdisplayEachBode)
        self.UIcheck2.grid(row=6, columnspan=3, sticky='W')

        self.msgLabel = tk.Label(self.bodeFrame, text="", width=50)
        self.msgLabel.grid(row=7, columnspan=4)

        self.idx=0
        atexit.register(self.scope.closeDev)
        self.window.mainloop()
        
    def msg(self, mess):
        #current_time_str = datetime.now().strftime("%H:%M:%S.%f")
        #print(current_time_str + " \t"+mess)
        print(mess)
        self.msgLabel.config(text=mess)
        if '?' in mess or '!' in mess:
            self.msgLabel.config(fg="red")
        else:
            self.msgLabel.config(fg="green")        
        

    def initFrq(self):        
        if (self.scope.isDevOpen() and self.rigol.isDevOpen()):            
            steps = int(self.steps.get())
            start_f = float(self.start_f.get())
            stop_f = float(self.stop_f.get())
            if (self.UIlinfrq.get() == 1):
                self.frq = np.linspace(start_f, stop_f, steps)
            else:
                self.frq = np.logspace(int(np.log10(start_f)), int(np.log10(stop_f)), steps)
                
            self.waits = np.maximum(((1/self.frq) * 10), 2) # Limit the wait times to at least 2 seconds for each element
            self.waits = np.ceil(self.waits).astype(int) #round up to nearest integer seconds
            self.mag = np.full(steps, np.NaN)
            self.phase = np.full(steps, np.NaN)

            for i in range(steps):
                print(str(round(self.frq[i],3))+"Hz   \t"+str(self.waits[i])+"s")
            totals=round( sum(self.waits) + len(self.frq)*3)
            print("--------------------------------------")
            print("in total appr. \t"+str(totals)+"s")

            self.filen = "bode_"+str(start_f)+"-"+str(stop_f)+"Hz_"+str(VOLT)+"V"
            
            with open(self.filen+".txt", 'w') as file:
                file.write("frequency (Hz)\tmagnitude (dB)\tphase (deg)\n")

            self.msg("Total time appr. "+str(round(totals/60,2))+"min. Click start again if scope screen full!")

            self.rigol.configSine(frequency=self.frq[0], ampl=VOLT, offs=0)
            self.msg("outputting "+str(VOLT)+"V sine at "+str(self.frq[0])+"Hz for "+str(self.waits[0])+"sec")
            self.scope.setVertical("C1", VOLT*1.25)
            self.adjustScopeHorizontal()
        
            self.startButton["command"] = self.stepBode
            
        else:
            self.msg("source/meter not yet ready!")

        

    def adjustScopeHorizontal(self):        
        duration = (1/self.frq[self.idx] * 10)
        self.scope.setTimeBase(duration)
        duration = self.scope.getTimeBase()
        self.msg("scope: 10*TDIV = "+str(duration)+"s set")
        self.waits[self.idx] = duration+2
        


    def stepBode(self):
        if (self.idx < len(self.frq)):        #until in range

            if (self.UIdisplayTimeFrq.get() == 1):
                (faxis, fu, fy) = self.scope.plotWF(self.frq[self.idx])
            else:
                self.scope.getWF()
                (faxis, fu, fy) = self.scope.calcSpectrum()                
            
            resp = np.divide(fy, fu);  # compute complex fourier transform out of the output's / input's
            # linearly interpolate the magnitude and phase values at the desired frequency
            self.mag[self.idx] = np.interp(self.frq[self.idx], faxis, 20*np.log10(np.abs(resp)))
            self.phase[self.idx] = np.interp(self.frq[self.idx], faxis, np.angle(resp, deg=True))


            with open(self.filen+".txt", 'a') as file:
                file.write(str(round(self.frq[self.idx],3))+"\t"+str(round(self.mag[self.idx],1))+"\t"+str(round(self.phase[self.idx],1))+"\n")

            if (self.UIdisplayEachBode.get() == 1):
                self.plotResp(faxis, resp, self.frq[self.idx])
            
            self.plotBode()

            self.idx+=1
            if (self.idx < len(self.frq)):   #if any
                self.rigol.changeFrq(self.frq[self.idx])
                self.msg("outputting "+str(VOLT)+"V sine at "+str(self.frq[self.idx])+"Hz")
                self.scope.manualVertical()
                self.adjustScopeHorizontal()

                self.window.after(int(self.waits[self.idx] * 1000), self.stepBode)
            else: #finished
                self.idx=0
                self.finishPlot()



    def cancel(self):
        print("cancelled")
        self.startButton["command"] = self.initFrq
        self.window.after_cancel(self.stepBode)
        self.msg("")
        self.idx = 0
        self.rigol.dg_send('OUTP OFF')

        
    def finishPlot(self):
        self.rigol.configSine(frequency=self.frq[0], ampl=VOLT, offs=0)
        self.rigol.dg_send('OUTP OFF')
        self.msg("finished sweeping through all "+str(len(self.frq))+" frequencies")
        self.startButton["command"] = self.initFrq
        with open(self.filen+".npy", 'wb') as f:
            np.save(f,self.frq)
            np.save(f,self.mag)
            np.save(f,self.phase)
            print(self.filen+" saved")
        self.window.after(3000, self.confirmation)

    def confirmation(self):
        self.plotBode(finalize=True)
        self.msg("data saved: "+str(self.filen)+"[.npy, .txt, .png]")
        self.scope.scpi_send("BUZZ BEEP")
            

    def loadFile(self):
        cdir = os.getcwd()  # Get the current directory
        file_path = filedialog.askopenfilename(initialdir=cdir, title="Select .npy file", filetypes=(("Numpy files", "*.npy"), ("All files", "*.*")))
        if file_path:
            print("opening:", file_path)
            try:
                with open(file_path, 'rb') as f:
                    self.frq = np.load(f)
                    self.mag = np.load(f)
                    self.phase = np.load(f)
                self.msg(file_path + " read.")
                self.plotBode(self)
            except Exception as e:
                print(e)
                print("could not load variables from file "+self.filen)

    def plotResp(self, faxis, resp, f_exc):
        plt.ion() #turn interactive plotting off            
        fig, ax = plt.subplots(nrows=2, ncols=1, squeeze=False, sharex='col', figsize=(10,8))
        fm=plt.get_current_fig_manager()
        fm.window.wm_geometry('1200x1000+0+0') #place the window on top left corner of screen
        plt.ion()
        ax[0][0].set_title("Bode-plot of CH2/CH1")
        ax[0][0].semilogx(faxis, 20*np.log10(np.abs(resp)), label='')
        ax[0][0].axvline(x=f_exc, color='r', linestyle=':', label="excitation frequency = "+str(f_exc)+"Hz")         # Add a vertical line at f_exc
        ax[0][0].legend()
        ax[0][0].set(ylabel='Magnitude (dB)')
        ax[0][0].grid()
        ax[1][0].semilogx(faxis, np.angle(resp)*180/np.pi)
        ax[0][0].axvline(x=f_exc, color='r', linestyle=':')
        ax[1][0].set(ylabel='Phase (deg)', xlabel='log10(frequency) (Hz)')
        ax[1][0].grid()
        plt.show(block=False)

    def plotBode(self, finalize=None):    
        plt.ion() #turn interactive plotting off
        if (self.figBode is None):
            self.figBode, self.axBode = plt.subplots(nrows=2, ncols=1, squeeze=False, sharex='col', figsize=(10,8))
        (fig, ax) = (self.figBode, self.axBode)
        fm=plt.get_current_fig_manager()
        fm.window.wm_geometry('1200x1000+0+0') #place the window on top left corner of screen
        plt.ion()
        ax[0][0].clear()
        ax[0][0].set_title("Bode-diagram of Y/U")
        ax[0][0].semilogx(self.frq, self.mag, 'r*-')
        ax[0][0].set(ylabel='Magnitude (dB)')
        ax[0][0].grid(True, which="both")

        ax[1][0].clear()
        ax[1][0].semilogx(self.frq, self.phase, 'r*-')
        ax[1][0].set(ylabel='Phase (deg)', xlabel='log10(frequency) (Hz)')
        ax[1][0].grid(True, which="both")
        plt.show(block=False)

        if (finalize is True): #if finished
            plt.pause(1) # Introduce a short delay for the plot to display
            fig.savefig(self.filen+".png")
        
    

def main():
    b = Bode()


if __name__ == '__main__':
    main()  
