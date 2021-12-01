import tkinter as tk
from datetime import datetime, timedelta
import winsound
frequency = 2500  # Set Frequency To 2500 Hertz
duration = 1000  # Set Duration To 1000 ms == 1 second
val = ["0", "100", "200", "250", "200", "100", "0",\
       "-100", "-200", "-250", "-200", "-100", "0"]
       
def min_rounder(t):
    # Rounds to next minute
    return (t.replace(second=0, microsecond=0) + timedelta(minutes=1))

class Application(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title('Counter')
        self.master.attributes("-topmost", True)
        self.create_widgets()
        self.i=[]
        self.step=0

    def create_widgets(self): 
        self.l = tk.Label(self.master, width=30, anchor="e", justify="right")
        self.l.grid(row=0, columnspan=3, sticky=tk.E)

        self.l3 = tk.Label(self.master, text="", font=("Arial",25))
        self.l3.grid(row=1)

        self.l2 = tk.Label(self.master, text="", width=30, anchor="e", justify="right")
        self.l2.grid(row=2)
        
        self.e = tk.Entry(self.master, text="", width=15)
        self.e.grid(row=2, column=1)

        self.b = tk.Button(self.master, text="start", command=self.start)
        self.b.grid(row=1, column=1)

        self.b2 = tk.Button(self.master, text="force", command=self.computeNext)
        self.b2.grid(row=2, column=2)


    def call(self):
        self.now = datetime.now()
        lstr = self.now.strftime("%Y-%m-%d %H:%M:%S")
        self.l.config(text=lstr) #change the text
        if (len(self.i)>1):
            tdiff = self.i[-1]-self.now
            s=int(tdiff.total_seconds())
            if (s>0):
                self.l3["text"]=s
                if (s==20 or s==12):
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
            else:
                self.computeNext()

        
        root.after(1000,self.call)

    def start(self):
        self.b.destroy()
        self.i.append(min_rounder(self.now))
        self.i.append(self.i[-1])
        print()
        print(self.i[-1].strftime("%Y-%m-%d %H:%M:%S"))
        self.computeNext()        
        self.e.focus_set()
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
        

    def computeNext(self):
        self.i.append(self.i[-1]+timedelta(minutes=3))
        starttime=self.i[-2].strftime("%H:%M")
        stoptime=self.i[-1].strftime("%H:%M")
        self.l2["text"]=starttime+" .. "+stoptime
        
        print(self.i[-3].strftime("%H:%M"), end =" ")
        print(self.e.get())
        self.e.delete(0,tk.END)
        self.e.insert(0,val[self.step]+" ")
        self.e.focus_set()
        self.step=min(self.step+1, len(val)-1)


if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    #app.mainloop()
    app.call() #call the function initially
