import tkinter as tk
from datetime import datetime, timedelta

def min_rounder(t):
    # Rounds to next minute
    return (t.replace(second=0, microsecond=0) + timedelta(minutes=1))

class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        self.i=[]

    def create_widgets(self): 
        self.l = tk.Label(self, width=30, anchor="e", justify="right")
        self.l.pack(side="top")
        self.l2 = tk.Label(self, width=30, anchor="e", justify="right")
        self.l2.pack(side="top")
        self.l3 = tk.Label(self, font=("Arial",25))
        self.l3.pack(side="top")
        
        self.e = tk.Entry(text="value:", width=6)

        self.b = tk.Button(self, text="start", command=self.start)
        self.b.pack(side="top")

        self.b2 = tk.Button(self, text="force", command=self.computeNext)
        self.b2.pack(side="top")

    def call(self):
        self.now = datetime.now()
        lstr = self.now.strftime("%Y-%m-%d %H:%M:%S")
        self.l.config(text=lstr) #change the text
        if (len(self.i)>1):
            tdiff = self.i[-1]-self.now
            if (tdiff.total_seconds()>0):
                self.l3["text"]= int(tdiff.total_seconds())
            else:
                self.computeNext()
        
        root.after(1000,self.call)

    def start(self):
        self.b.destroy()
        self.i.append(min_rounder(self.now))
        print(self.i[-1].strftime("%Y-%m-%d %H:%M:%S"))
        self.computeNext()
        self.e.pack(side="right")
        self.e.focus_set()

    def computeNext(self):
        self.i.append(self.i[-1]+timedelta(minutes=3))
        self.l2["text"]=self.i[-1].strftime("%H:%M:%S")
        print(self.e.get())
        print(self.l2["text"], end =" ")
        if (self.e.get()):
            self.e.select_to(len(self.e.get()))

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(master=root)
    #app.mainloop()
    app.call() #call the function initially
