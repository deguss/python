import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk

import pyvisa
import time
import math         
#----------------------------------------------------------
class Rigol(tk.Frame):
#----------------------------------------------------------

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)   
        self.parent = parent        
        
        self.timeout=0
        self.tim=0
        self.dev=0
        
        # Start pyvisa and print the resources found
        self.rm = pyvisa.ResourceManager()
        self.ports = self.rm.list_resources()

        self.initUI()

    def initUI(self):
        # create GUI inside parent frame
        self.pack(fill=tk.BOTH, expand=1)
        
        boxname = tk.Label(self, text="Function Generator", font=("Arial", 16)) #title
        boxname.pack(padx=10, pady=10)


        choicesvar = tk.StringVar(value=self.ports)
        self.lbox = tk.Listbox(self, listvariable=choicesvar, width=35, height=6, activestyle='none', font=("Courier", 10))
        self.lbox.bind("<Double-1>", self.chooseDev) #register doubleclick action
        self.lbox.pack(padx=10, pady=10)


        self.openButton = tk.Button(self, text="open resource", command=self.chooseDev)
        self.openButton.pack(padx=10, anchor=tk.E)

        self.closeButton = tk.Button(self, text="close resource", command=self.closeDev, state=tk.DISABLED) #combine_funcs())
        self.closeButton.pack(padx=10, anchor=tk.E)
       

        self.msgLabel = tk.Label(self, text="")
        self.msgLabel.pack(padx=10, anchor=tk.W)

        self.dispLabel = tk.Label(self, text="")
        self.dispLabel.pack(padx=10, anchor=tk.S)

        self.inpBox = tk.Entry(self, width=20, state=tk.DISABLED, font=("Arial", 11))
        self.inpBox.pack(padx=10, pady=10)
        self.inpBox.bind('<Return>', self.onEnter)

    def onEnter(self, *args):
        m=self.inpBox.get()
        self.dg_send(m)
        self.inpBox.delete(0, tk.END)
        
 
    def chooseDev(self, *args):      
        idxs = self.lbox.curselection()
        if (self.isDevOpen() == False): #if not yet open
            if(len(idxs)==1):
                p=self.ports[int(idxs[0])]
                
                if(self.openDev(p) == False):
                    self.msg("Right resource? Instrument turned on?")

            else:
                self.msg("please select a valid resource!")

    def openDev(self, p):
        timeout=0
        self.dev = self.rm.open_resource(p)
        usb=p.split('::')
        
        self.dg_send('*IDN?')
        idn=self.dev.read()
        dg=idn.split(',')
        #print(dg)

        if ("RIGOL" in dg[0]):
            #pdb.set_trace()
            self.msg(usb[0]+" ("+dg[0]+" "+dg[1]+") opened")
            self.openButton.configure(state=tk.DISABLED)
            self.closeButton.configure(state=tk.NORMAL)
            self.lbox.configure(state=tk.DISABLED)
            self.inpBox.configure(state=tk.NORMAL)
            self.inpBox.delete(0, tk.END)
            self.inpBox.insert(0,"OUTP ON")
            self.inpBox.focus()  
            return True
        else:
            self.msg("Failed to open resource "+p+"!")
            return False   


    def dg_send(self, message):
        """
        Sends a command to the RIGOL DG1022.
        It also calculates the time needed for the message to be transmitted.
        Time estimates may be over-conservative.
        The function does not return anything.
        :param message: The command to be sent
        :type message: str
        """
        self.dev.write(message)
        delay = max(0.001 * len(message), 0.2)
        time.sleep(delay)
        
    def configSine(self, frequency, ampl, offs):
        self.dg_send('OUTP OFF')  # Switch CH1 off
        self.dg_send('APPL SIN')
        self.dg_send('FREQ ' + str(frequency))  # Set the frequency
        self.dg_send('VOLT:UNIT VPP')  # Set VPP mode
        self.dg_send('VOLT ' + str(ampl))  # Set Vpp
        self.dg_send('VOLT:OFFS' + str(offs))
        self.dg_send('OUTP ON')  # Turn CH1 on

    def changeFrq(self, frequency):
        self.dg_send('FREQ ' + str(frequency))           

    def changeAmpl(self, ampl):
        self.dg_send('VOLT ' + str(ampl))   


        
    def msg(self, mess):
        self.msgLabel.config(text=mess)
        if '?' in mess or '!' in mess:
            self.msgLabel.config(fg="red")
        else:
            self.msgLabel.config(fg="green")

    def isDevOpen(self):
        if (self.dev):
            return True
        else:
            return False        


    def closeDev(self):
        if (self.isDevOpen()):
            self.dev.close()

        self.dev=0
        self.msg("resource closed")
        self.lbox.configure(state=tk.NORMAL)
        self.openButton.configure(state=tk.NORMAL)
        self.closeButton.configure(state=tk.DISABLED)
        self.dispLabel.configure(text="")
        self.inpBox.configure(state=tk.DISABLED)
        self.timeout=0
        self.idx=0

        
class App():
    def __init__(self):
        window = tk.Tk()
        window.geometry("700x400")
        window.title("Test Rigol")
        
        frame = tk.Frame(master=window, height=250, width=250, highlightbackground="gray", highlightthickness=1)
        frame.pack(side=tk.LEFT, padx=10, pady=10)
        self.rigol = Rigol(frame)


        window.mainloop()

        
if __name__ == "__main__":
    w = App()


                     





