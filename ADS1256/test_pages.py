import tkinter as tk
import tkinter.ttk as ttk
 
class NotebookPage(tk.Frame):
    def __init__(self, parent, name, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        parent.add(self, text=name)
 
class Page1(NotebookPage):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, "Page 1", *args, **kwargs)
        tk.Label(self, text="This is page 1", bg=self["bg"]).pack(padx=10, pady=10)
 
class Page2(NotebookPage):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, "Page 2", *args, **kwargs)
        tk.Label(self, text="This is page 2", bg=self["bg"]).pack(padx=10, pady=10)
 
class MyWindow(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        notebook = ttk.Notebook(self)
        notebook.pack(padx=5, pady=5)
        Page1(notebook, bg="yellow")
        Page2(notebook, bg="light blue")
 
MyWindow().mainloop()
