from tkinter import Tk, Label, Button, Checkbutton, IntVar
#    ^ Use capital T here if using Python 2.7

def ask_duration(prompt, options):
    root = Tk()
    root.attributes('-topmost', True)
    if prompt:
        Label(root, text=prompt).pack()
    v=[]
    for i, o in enumerate(options):
        v.append(IntVar(value=1))
        cb=Checkbutton(root, text=o, variable=v[-1])
        #a.select()
        cb.pack(anchor="w")
        
    Button(text="go", command=root.destroy).pack()
    root.mainloop()
    result = [ ing for ing, cb in zip( options, v ) if cb.get()>0 ] 
    return result

if (__name__ == "__main__"):
    result = ask_duration("How many hours of data should each plot be made of?",
                    ["10min", "1h", "6h", "12h", "24h"])
    print(result)
