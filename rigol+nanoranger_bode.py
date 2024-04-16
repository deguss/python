import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
import pdb
import collections
import math
from tempfile import TemporaryFile
outfile = TemporaryFile()

from rigol import *
from nanoranger import *




START_F = 1
STOP_F = 150
STEPS = 100


class Bode():
    def __init__(self):

        self.filen = "1_150_100.npy"
        
        window = tk.Tk()
        window.geometry("700x400")
        window.title("Frequency response analyzer")

        topFrame = tk.Frame(master=window)  # Added "container" Frame.
        topFrame.pack(side=tk.TOP, fill=tk.X, expand=1, anchor=tk.N)
                
        frame1 = tk.Frame(master=topFrame, height=250, width=250, highlightbackground="gray", highlightthickness=1) # create the left frame
        frame1.pack(side=tk.LEFT, padx=10, pady=10)
        self.nano = NanoRanger(frame1)   
        
        frame2 = tk.Frame(master=topFrame, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        frame2.pack(side=tk.LEFT, padx=10, pady=10)
        self.rigol = Rigol(frame2)

        botFrame = tk.Frame(master=window)
        botFrame.pack(side=tk.BOTTOM, fill=tk.X, expand=1, anchor=tk.S)
        
        startButton = tk.Button(botFrame, text="start analysis", command=self.bode)
        startButton.pack()

        loadFile = tk.Button(botFrame, text="display results", command=self.loadFile)
        loadFile.pack()

        self.idx=0

        window.mainloop()

    def bode(self):
        self.frq = np.logspace(math.log10(START_F), math.log10(STOP_F), STEPS)
        u=len(self.frq)
        self.max=np.zeros(u)
        self.rms=np.zeros(u)
        self.mean=np.zeros(u)
        self.std=np.zeros(u)
        waits = 10 * 1/self.frq
        waits[waits<10]=10
        self.waits=np.ceil(waits).astype(int) #round up to nearest integer seconds
        totals=round( sum(self.waits) + len(self.frq)*1.2)
        print("max(period) = "+str(round(max(self.waits)))+"s, in total "+str(totals)+"s")
        print("in progress")

        if (np.nanmax(self.nano.getBuf())  and #some data is getting in
            self.rigol.isDevOpen() ):  #and function generator is ready

            self.nano.resetBuf(self.waits[0]*3)
            self.rigol.configSine(frequency=self.frq[0], ampl=0.05, offs=0.025)
                        
            t1 = threading.Timer(self.waits[0], self.timerCallBack)
            t1.start()
        else:
            print("something not yet ready")
            

    def timerCallBack(self):
        i = self.idx
        if (i < len(self.frq)):        #until in range
            data=self.nano.getBuf()                 #get data
            self.max[i]=np.nanmax(data)            #save max value
            self.rms[i]=np.sqrt(np.mean(pow(data,2)))   #save rms
            self.mean[i]=np.mean(data)
            self.std[i]=np.std(data)

            i+=1                      #step up to next
            if (i < len(self.frq)):   #if any
                self.rigol.changeFrq(self.frq[i])     
                self.nano.resetBuf(self.waits[i]*4)   
                print(".", end="")
                t1 = threading.Timer(self.waits[i], self.timerCallBack)
                t1.start()
            else: #finished
                i=0
                self.finishPlot()
                #updatePlot()
        self.idx = i

    def finishPlot(self):
        with open(self.filen, 'wb') as f:
            np.save(f,self.frq)
            np.save(f,self.max)
            np.save(f,self.rms)
            np.save(f,self.mean)
            np.save(f,self.std)
            print(self.filen+" saved")

    def loadFile(self):
        with open(self.filen, 'rb') as f:
            frq = np.load(f)
            maxs = np.load(f)
            rms = np.load(f)
            mean = np.load(f)
            stds = np.load(f)
        plt.plot(frq,maxs, 'b.', label='peak')
        plt.plot(frq,rms, 'g.', label='rms')
        plt.plot(frq,mean, 'r.', label='mean')
        plt.plot(frq,stds, 'c.', label='std') #blue green red cyan magenta yellow
        plt.gca().legend()
        plt.title('amplitude response')
        plt.ylabel('amplitude')
        plt.xscale('log')
        plt.xlabel('log(frq)')
        plt.grid(True)
        plt.show()
            
        
    def updatePlot(self):
        1

    def plotBode(self):    
        plt.ion() #turn interactive plotting off
        fig = plt.figure()
        ax = fig.add_subplot(111)
        plt.yscale('log')
        plt.grid(True)
        line1, = ax.plot(0.1, 1, '.r')

    

def main():
    b = Bode()
    


if __name__ == '__main__':
    main()  
