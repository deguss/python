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

from lecroy import *

class App():
    def __init__(self):
        self.window = tk.Tk()
        self.window.geometry("700x400")
        self.window.title("FFT")
        
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
