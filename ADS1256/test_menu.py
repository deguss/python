import tkinter as tk

root = tk.Tk()

menuBar = tk.Menu(root)
menu1 = tk.Menu(root)
submenu = tk.Menu(root)
submenu.add_radiobutton(label="Option 1")
submenu.add_radiobutton(label="Option 2")

menuBar.add_cascade(label="Menu 1", menu=menu1)
menu1.add_cascade(label="Subemnu with radio buttons", menu=submenu)

root.config(menu=menuBar)
root.mainloop()
